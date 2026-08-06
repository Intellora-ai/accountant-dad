# GATE · REQUIREMENTS

**Fires when:** anyone says *"make it faster / better / more accurate / smarter"*,
before any build starts, and whenever a target arrives without a number.

**A vague target is not a requirement. It is a request for a number** (Law 52), and
the obligation to get that number is the engineer's, not the owner's.

```
X  "make it a bit faster"  ->  500ms  ->  495ms  ->  argument
Y  "make it faster"        ->  "to what number?"  ->  "under 200ms"  ->  build
```

**Stop and ask for the number. Never infer it. Never pick one yourself.** A change
with no measurable target has no definition of done, which makes Laws 6, 7, 30 and 51
unenforceable at once.

---

## THE ORDER — never design from a solution

```
WHY (need)  ->  WHAT (requirement)  ->  HOW (design)  ->  implementation
```

Never HOW → WHY.

## THE CHAIN — nothing orphaned

```
Need  ->  Requirement  ->  Architecture  ->  Implementation  ->  Test  ->  Validation
```

Every link traces both ways. An implementation with no requirement above it is
unscoped work. A requirement with no test below it is an opinion.

---

## EVERY `SHALL` STATEMENT — eight properties, all of them

| Property | Fails when |
|---|---|
| **Necessary** | removing it changes nothing |
| **Atomic** | it contains "and" joining two testable claims |
| **Measurable** | it has no number and no unit |
| **Unambiguous** | two engineers would build different things from it |
| **Verifiable** | no Inspection / Analysis / Demonstration / Test can settle it |
| **Traceable** | no need above it, no test below it |
| **Solution independent** | it names a tool, a library or a mechanism |
| **Achievable** | nothing in the constraints permits it |

## EVERY REQUIREMENT CARRIES

```
Requirement          the SHALL statement
Reason               the need it serves — WHY, in one line
Owner                a PERSON, never a department
Verification method  Inspection | Analysis | Demonstration | Test
Metric               the quantity, with its unit
Acceptance criteria  the threshold, and which side of it passes
Traceability         the need above, the test below
```

## BANNED WORDS — unless a number follows

```
fast · better · efficient · reliable · easy · scalable · optimized · robust
clean · significant · high · smart · accurate · soon · a bit more
```

Every adjective hides a claim. Two questions settle it: **what observation would prove
this false?** and **what do I do differently at each value?** No answer to either → the
word is doing no work. Cut it.

**Symmetric obligation: never claim an improvement without before/after numbers.**
*"Should be faster"* is banned exactly as *"should work"* is.

---

## UNDEFINED TERMS — Law 54

Never build on a word with no definition. *Intelligence · Confidence · Understanding ·
Correct · Safe · Risk · Doubt · Uncertainty · Mastery · Accuracy · Reliability ·
Latency · Success · Failure.*

**Never invent the definition yourself. Ask.** A definition chosen silently by the
engineer is a decision the owner never made.

```
not measurable  ->  not provable  ->  not true  ->  FALSE
```

Register every definition in [`../DEFINITIONS.md`](../DEFINITIONS.md).

---

**Purpose:** the execution plan under an approved architecture. The architecture says what is allowed; the blueprint says what gets built and in what order. **If they conflict, architecture wins.**

### A good blueprint is:

1. **Steps in order**, each small and finished completely before the next starts.
2. **Each step is checkable** before moving on — problems get caught early, not at the end.
3. **Each step has an undo.**
4. It has **stop points / checkpoints** where work halts for review.
5. It lists **what could go wrong** — per step, not globally.
6. **So clear anyone can follow it** — no questions, no guesses, every step spelled out.
7. **Starts with the smallest real thing**, not the whole vision.
8. **Ship it → test it for real → it must pass a measurable real number → then expand.**
9. **Never breaks existing working things** while expanding.

### It contains:

**H1. Goal** — what, why, and the **measurable finish line** (Law 52). The same number as G2.

**H2. Non-Goals** — what this build will NOT do. Copied from G9 and expanded with anything discovered while planning.

**H3. Dependencies** — what this needs, and what needs this. Both directions. A dependency nobody declared is the most common cause of a broken build.

**H4. Acceptance Criteria** — success from the **user's** point of view, not the system's. Each criterion is a sentence a non-engineer can read and judge. Each has a number.

**H5. The Plan** — deliverables broken down: code · tests · docs · APIs · UI. Then **build order**, phase by phase, with the reason each phase must come before the next.

**H6. Per-phase definition of done** — for each phase, what must be true before the next phase starts. Not "it works" — the number.

**H7. The Build → Verify → Fix loop** (§I) — how the loop runs for this build specifically, including what "green" means here.

**H8. Stop Points** — the moments where work halts and the user reviews before continuing. At minimum: after architecture approval, after the first phase ships, before anything touches production data.

**H9. Per-step Risks + Rollback** — for every step: what could go wrong, how you would know, and the exact undo. A step with no undo does not get built until it has one (Law 8).

**H10. Definition of Done** (§N) — the full DONE GATE for this build.

---


---

## CHECKLIST

- [ ] Need stated — WHY, before WHAT
- [ ] Current state MEASURED, desired state MEASURABLE, gap stated
- [ ] Every SHALL passes all eight properties
- [ ] Every requirement names its verification method
- [ ] Every number carries its unit
- [ ] Zero banned words without a number
- [ ] Every load-bearing term defined and registered
- [ ] Traceability closed both directions — nothing orphaned
- [ ] Non-goals written down
- [ ] Every step has an undo (Law 8)
