# GATE · INVESTIGATION

**Fires when:** a bug, a failure, a red check, an unexpected result, *"why is this
slow"*, or any write to `KNOWN_FAILURES.md`.

**Run [`../METHOD.md`](../METHOD.md) stages 1–12. This gate is what they produce when
the subject is a defect.**

---

## THE FIRST MOVE IS NOT A FIX

```
A red error STOPS everything.  Do not build on broken.
```

And do not fix the first thing you find. The first thing you find is a symptom in
almost every case that matters.

---

## THE PROCEDURE

### 1 · Reproduce, and reproduce cheaply

Shrink before you solve. **What is the smallest version that still fails?** A cheaper
test that fails in the same place as the expensive one is the whole return — if the
cheap version fails, you just saved the expensive one.

### 2 · State current vs expected, both measured

Not "it's broken". What was observed, what was expected, and the command that produced
each.

### 3 · List EVERY candidate cause — not the likely one

Write them all down before measuring any. A list of one is a guess with paperwork.

### 4 · Measure each. Reject only with evidence

```
candidate  ->  the observation that would refute it  ->  run it  ->  MEASURED verdict
```

**A REJECTED hypothesis stays rejected unless NEW evidence appears.** Re-opening a
disproved hypothesis costs a full cycle and has done so here.

### 5 · WHY upward to the highest layer you can change

Stop only when the next WHY is product, legal, physics or owner territory. **If the
root is a whole CLASS, fix the class**, not the instance.

### 6 · Invert

*"If I wanted this failure to be permanent and invisible, how would I build it?"*
Whatever the system already matches is a confirmed bottleneck.

### 7 · Audit the assumptions the investigation itself made

Including the ones inherited from a document. **A document is a hypothesis, never
evidence — read the code.**

### 8 · Fix the cause. Then state the new failure the fix could create

### 9 · Write the permanent test BEFORE the fix is complete (Law 3)

It must fail before the fix and pass after, and it guards the class forever.

### 10 · Extract the principle

Name the general root cause so the whole CLASS cannot recur — then record it in
`LESSONS.md`.

---

## THE QUESTIONS, ASKED EVERY TIME

```
What actually happened?
Has it happened before?
If it repeats — what SYSTEM produces it?
Who is deciding? Who is blind?
Which assumption became a fact?
What measurements exist? Which ones DON'T?
What don't I know?
Am I solving the right problem?
What is slow? How slow? Compared to what? How measured?
What number changes if this is solved perfectly?
```

**If you cannot answer with numbers, you do not understand the problem yet.**

---

## WRITING IT DOWN — `KNOWN_FAILURES.md`

Every entry carries a **machine-checkable predicate** and a state a program can read:
`OPEN` · `PARTIAL` · `BLOCKED` · `CLOSED`. An entry with no predicate does not parse
and cannot be added.

**Polarity is the point.** Write the predicate so it stops holding when the status
stops being true:

```
OPEN    -> assert the DEFECT is still there
CLOSED  -> assert the FIX is still there
```

Written the other way round, an entry can be fixed and stay OPEN forever — which is
exactly what happened to F-024.

**Hedges are refused by a hook here.** `probably` · `I think` · `should work` ·
`likely because` · `presumably` · `I assume` are blocked from the truth documents,
because a false claim in one of them is later read as evidence. Measured 2026-08-06:
two of three testable claims in `KNOWN_FAILURES.md` were FALSE, and one reached a
root-cause analysis as if verified.

Write what you MEASURED, or write UNKNOWN. Both are correct. A hedge is not.

---

## FINISH

Stop **only** when the cause is ELIMINATED, or an external blocker is PROVEN.

**Never stop at an explanation.** An identified root cause is not a fixed one, and
reporting one as though it were is the most common way an investigation fails.

---

## CHECKLIST

- [ ] Reproduced, on the smallest case that still fails
- [ ] Current and expected both MEASURED, with the commands quoted
- [ ] EVERY candidate cause listed, not just the likely one
- [ ] Each measured; each rejection carries its evidence
- [ ] WHY taken to the highest changeable layer
- [ ] Inversion applied
- [ ] The investigation's own assumptions audited
- [ ] Root cause ELIMINATED, not merely explained
- [ ] Permanent regression test written, watched RED first
- [ ] Class-level principle extracted to `LESSONS.md`
- [ ] New failure the fix could create — stated
- [ ] `KNOWN_FAILURES.md` entry has a correctly-polarised predicate
