# ENGINEERING_METHOD.md

**Mandatory. Enforced by the repository, not by anyone's memory.**

Loaded automatically by `.claude/hooks/engineering_method.py` at session start,
before every prompt, and before every tool call. Both the hook and its
registration are tracked by git, so a fresh clone carries them.

---

## Why this file exists — the measurement that forced it

`.gitignore:50` ignored `.claude/` wholesale. Measured 2026-08-06:

```
$ git ls-files .claude/
(empty)
```

Every hook enforcing this project's rules lived in `~/.claude/` on **one
laptop**. A fresh clone, a second machine, or a wiped home directory got zero
enforcement. The rules survived only because one home directory still existed.

**"CLAUDE.md is not enough" was the wrong diagnosis.** The document was fine.
Nothing in the repository read it, and nothing in the repository could report
that nothing read it.

---

## The method

### 1 · DEFINE

```
Current State  ->  Desired State  ->  Gap
```

No gap, no engineering. A problem is not a solution. If all three cannot be
stated measurably, the problem is not understood yet.

### 2 · MEASURE BEFORE CONCLUDING

Every claim is exactly one of:

```
MEASURED    an observation was made; the command that produced it is quoted
DERIVED     follows from a measurement by stated arithmetic
INFERRED    plausible, NOT observed - and labelled as such
UNKNOWN     the honest answer, and always an acceptable one
```

**A DOCUMENT IS A HYPOTHESIS, NEVER EVIDENCE.** Read the source. This rule
exists because it was broken: root cause "R4" was derived from
`KNOWN_FAILURES.md`'s *wording* and destroyed the moment the code was read —
the pipeline had no PDF special case at all, only two total mappings.

Measured the same day: **two of three testable claims in `KNOWN_FAILURES.md`
were FALSE.**

### 3 · ROOT CAUSE — BOTH DIRECTIONS, EVERY TIME

**WHY, upward** until the highest layer you can actually change. Stop only when
the next WHY is product, legal, physics or owner territory.

**HOW, downward** from the perfect outcome to the smallest executable step.

One direction alone produces either an unactionable insight or a patch.

### 4 · INVERT

> *"If I wanted this to fail forever, how would I design it?"*

Whatever the current system already matches is a real bottleneck. Remove those
first. Applied 2026-08-06, it described the system exactly: hide failures inside
an all-or-nothing measurement, drop crashes silently from the denominator, throw
away the crop origin, maintain the defect list by hand.

### 5 · ALL CAUSES, NOT THE FIRST ONE

List every candidate. Measure each. **Reject only with evidence, never with
intuition.** Record rejections — a REJECTED hypothesis stays rejected unless
NEW evidence appears. Re-opening a disproved hypothesis is a defect.

### 6 · PARALLEL BY DEFAULT

Independent work is dispatched concurrently. Serial investigation of
independent problems is a defect, not a style.

### 7 · FINISH

Stop **only** when the cause is ELIMINATED, or an external blocker is PROVEN.

Never stop at an explanation. An identified root cause is not a fixed one.

### 8 · DESIGN AGAINST THE NEXT FAILURE

Every fix states the new failure it could create. Measured instance: fixing
F-028's geometry introduced a **663x** file-size regression, because replacing a
library call replaced its defaults — and the fix's own test could not see it,
since that test asserted page size in points and the geometry was right in both
worlds.

**A test can only fail on what it looks at.**

---

## What the enforcement can and cannot do

| Surface | Can it refuse? | Evidence |
|---|---|---|
| `SessionStart` | no | stdout prepended once per session |
| `UserPromptSubmit` | no | stdout prepended to every prompt |
| `PreToolUse` | **YES** | a non-zero exit blocks the call — the Law 56 hook refused a `Write` in this repository |
| `CLAUDE.md` | no | read only if the session reads it |

**The honest boundary:** a hook can force the rules to be SEEN, and can refuse
specific mechanical violations. **It cannot make anyone reason well.** Claiming
otherwise would be the same unmeasured assertion this method exists to prevent.

What it removes is the failure where the method was never loaded at all.

**The one mechanical rule enforced:** a hedge — *"probably"*, *"I think"*,
*"should work"* — written into `KNOWN_FAILURES.md`, `PROGRESS.md`, `STATE.md`
or `BLOCKERS.md` is refused. Those four are read later **as evidence**, and a
false claim in them becomes an engineering decision.

---

## Verification

`tests/unit/test_engineering_method_enforced.py`, ten assertions:

- the hook and its registration are **tracked by git** (`git ls-files`, not
  `Path.exists` — a file on this disk and absent from the repository is exactly
  the defect)
- **no worktree or local state** was committed by the un-ignore
- each of the three events is registered
- the guard **refuses** a hedge in a truth document — observed refusing, not
  assumed to
- the guard **permits** a measured statement in the same file
- the guard **ignores** ordinary files
- the advisory events emit the method and never block a turn
