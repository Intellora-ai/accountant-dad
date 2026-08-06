# METHOD — the thinking engine

**Runs on every engineering problem, without being asked.** Architecture, debugging,
requirements, investigation, review, tool choice, trade-off, estimate. All of them.

**These are not questions to put to the owner.** They are reasoning the engineer does
silently and shows the *results* of. Ask the owner only when a genuinely unrecoverable
answer blocks the work (§E.3): a number only they can set (Law 52), a term only they
can define (Law 54), or an irreversible choice.

---

## THE PIPELINE

Twelve stages, run in order. Skipping one is a defect, not a style. The order matters
more than any single stage: **Question → Delete → Simplify → Accelerate → Automate**
run out of order is how you make the wrong thing cheaper to keep.

```
 1 FRAME          am I solving the right problem?
 2 PERFECT        what must ALL be true for the perfect outcome to exist?
 3 CURRENT        what is true now — MEASURED, not recalled
 4 GAP            the engineering problem is exactly Current -> Desired
 5 WHY (up)       to the highest layer that can actually be changed
 6 HOW (down)     from the perfect outcome to the smallest executable step
 7 INVERT         what would guarantee failure? Whatever already matches is real
 8 BOTTLENECK     list EVERY candidate. Measure each. Reject only on evidence
 9 ASSUMPTIONS    what did I assume? How do I know? What would prove me wrong?
10 SYSTEMS        which interaction causes this? What must flow — and what must not
11 TRANSFORM      convert the hard problem into an easier equivalent one. Then delete
12 FUTURE         if this ships, what breaks next? Then hand to gates/VERIFICATION.md
```

---

## 1 · FRAME — the right problem

The stated problem is almost always one layer above the real one. Before anything:

- What actually happened? Has it happened before?
- **If it repeats, what SYSTEM produces it?** A recurring fault is a process defect
  wearing an incident's clothes.
- Who is deciding? Who is blind? Which assumption already became a fact?
- **What number changes if this is solved perfectly?** No such number → the objective
  is incomplete, and no amount of work will settle whether it succeeded.

**Solving the wrong problem well is the most expensive outcome available.**

## 2 · PERFECT OUTCOME

*"What does done and great look like?"* — then the harder half: **what must ALL be
true for it to exist?** Not one condition. Every condition. The one you skip is the
one that fails in production.

Write it before deciding anything. A perfect outcome written after the design is a
justification, not a target.

## 3 · CURRENT STATE — measured

Every claim carries exactly one label:

```
MEASURED    an observation was made; the command that produced it is quoted
DERIVED     follows from a measurement by stated arithmetic
INFERRED    plausible, NOT observed — and labelled as such
UNKNOWN     the honest answer, and always an acceptable one
```

**A DOCUMENT IS A HYPOTHESIS, NEVER EVIDENCE. Read the source.**

Measured 2026-08-06: two of three testable claims in `KNOWN_FAILURES.md` were FALSE,
and one was carried into a root-cause analysis as if verified. It produced root cause
"R4", which measurement then destroyed — the pipeline had no PDF special case at all.

**UNKNOWN outranks a plausible guess.** Unknown is a valid engineering state; a
confident wrong state is not.

## 4 · GAP

```
Current State  ->  Desired State  ->  Gap
```

If both ends are not stated measurably, **the problem is not defined and no work
starts.** No gap, no engineering.

## 5 · WHY, upward

Ask WHY until the **highest layer you can actually change**. Stop only when the next
WHY is product, legal, physics or owner territory.

"5 Whys" is a mindset, not a count — some causes are 5 deep, some 12. **If the root is
a whole CLASS, fix the class**, not the instance.

## 6 · HOW, downward

Reverse-engineer from the perfect outcome:

```
Perfect outcome  ->  how?  ->  how?  ->  how?  ->  the smallest executable step
```

WHY alone produces an unactionable insight. HOW alone produces a patch. **Both
directions, every time.**

## 7 · INVERT

> *"If I wanted this to fail forever, how would I design it?"*

Whatever the current system **already matches** is a real bottleneck. Remove those
first — they are proven, not hypothesised.

Applied 2026-08-06, it described the system exactly: hide failures inside an
all-or-nothing measurement, drop crashes silently from the denominator, throw away the
crop origin, maintain the defect list by hand. All four were real.

## 8 · BOTTLENECK — all candidates, measured

**Never assume one bottleneck. List every candidate.** Then, for each:

> *How do I KNOW this is the bottleneck? Measured, or guessed?*

Only measurements count. **Optimising a non-bottleneck yields exactly zero and feels
productive.**

Rejections are recorded. **A REJECTED hypothesis stays rejected unless NEW evidence
appears** — re-opening a disproved one is a defect and costs a full cycle.

Watch for the case where **the person asking is the bottleneck** — a decision only
they can make, hidden behind a wall of work you can control. Say it plainly.

## 9 · ASSUMPTION AUDIT

List them. For each, three questions:

| | |
|---|---|
| How do I know? | observed · measured · guessed — pick one, out loud |
| What evidence would prove me WRONG? | then go look for **that**, specifically |
| Who owns it? | a requirement nobody owns is an assumption that got promoted |

**Most things called constraints are assumptions in costume.** Physics, law and
arithmetic are constraints. Everything else is negotiable.

Confirming evidence is cheap and everywhere. **A conclusion you only tried to support
is unproven.**

## 10 · SYSTEMS

Never optimise parts in isolation. Optimise interactions.

- What **relationship** causes this?
- What information must each component **receive**?
- What information must it **NEVER receive**? (this is the one people skip, and it is
  where boundary defects live)
- Which interaction creates the failure?
- What else changes? Which modules? What future complexity?

Think in systems, not events. An event is one sample of a system.

## 11 · TRANSFORM, then SIMPLIFY

**Never attack a hard problem directly.** Convert it into an easier equivalent problem
with the same answer (Law 53).

- What is the smallest version that touches reality?
- Which single case, if it works, tells you the rest will?
- Is there a cheaper test that fails in the same place as the expensive one?

This project already did it once: a human accountant reads and simply *knows* —
copying that mechanism gives one model that reads and posts, and an unsolvable
verification problem. The transform gave **six engines, each with a narrow checkable
job.** Same outcome, far easier problem.

Then delete. **Delete until something breaks. If you did not have to add ~10% back,
you stopped early.** Fewer parts, fewer bugs. Can five rules become one? Can one
system replace five documents?

## 12 · FUTURE FAILURE

**Every fix states the new failure it could create.** Design for the current and the
next problem simultaneously.

Measured: fixing F-028's geometry introduced a **663×** file-size regression, because
replacing a library call replaced its defaults — and the fix's own test could not see
it, since that test asserted page size in points and the geometry was right in both
worlds.

**A test can only fail on what it looks at.**

Then hand off to [`gates/VERIFICATION.md`](gates/VERIFICATION.md): how will this be
tested, how will it fail, how will it be measured, how will it be rolled back?

---

## FINISH

Stop **only** when the cause is ELIMINATED, or an external blocker is PROVEN.

**Never stop at an explanation.** An identified root cause is not a fixed one.

Independent work is dispatched **concurrently**. Serial investigation of independent
problems is a defect, not a style.

---

## COVERAGE — every model that used to live somewhere else

Proof this is a merge, not a rewrite that quietly dropped things.

| Source | Where it now lives |
|---|---|
| §D.1 Perfect Outcome | stage 2 |
| §D.2 First Principles | stages 1, 5 |
| §D.3 5 Whys | stage 5 |
| §D.4 Inversion | stage 7 |
| §D.5 Systems Thinking | stage 10 |
| §D.6 Bottleneck | stage 8 |
| §D.7 Reverse Engineer | stage 6 |
| §D.8 Simplicity | stage 11 |
| §D.9 Trade-offs | [`gates/DECISION.md`](gates/DECISION.md) |
| §D.10 Evidence | stage 3 |
| §D.11 Second-Order | stage 12 |
| §D.12 Verification | [`gates/VERIFICATION.md`](gates/VERIFICATION.md) |
| §D.13 Falsification | stages 7, 9 |
| §D.14 Problem Transformation | stage 11 |
| old METHOD 1 DEFINE | stages 3, 4 |
| old METHOD 2 MEASURE | stage 3 |
| old METHOD 3 ROOT CAUSE | stages 5, 6 |
| old METHOD 4 INVERT | stage 7 |
| old METHOD 5 ALL CAUSES | stage 8 |
| old METHOD 6 PARALLEL | FINISH |
| old METHOD 7 FINISH | FINISH |
| old METHOD 8 FUTURE | stage 12 |
| Define concepts before building (Law 54) | [`DEFINITIONS.md`](DEFINITIONS.md) |
| Requirements engineering | [`gates/REQUIREMENTS.md`](gates/REQUIREMENTS.md) |
| Measurement discipline (Laws 44/52/56) | [`gates/MEASUREMENT.md`](gates/MEASUREMENT.md) |
| Root-cause / investigation procedure | [`gates/INVESTIGATION.md`](gates/INVESTIGATION.md) |

**Nothing was dropped.** That claim is checked by
`tests/unit/test_engineering_os.py::test_every_mental_model_has_a_home`.
