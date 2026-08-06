# LAWS — the 57

**Canonical. This is the ONLY copy.** Every other mention in this repository is a
link to here. Duplication was the measured defect that created this file:
`SYSTEM_LAWS.md` said *"55 numbered engineering laws"* while the constitution had
**57**, and nothing in the repository could notice the drift.

```
laws=57            measured at commit 00c6b8d by tools/ci/engineering_os.py
```

That line is machine-checked by `tests/unit/test_engineering_os.py`, so it cannot be
the next thing here to go stale.

**Precedence:** `docs/SYSTEM_INVARIANTS.md` › locked architecture (`docs/`) › **these
laws** › [`METHOD.md`](METHOD.md) and [`gates/`](gates/) › READMEs. **Locks win.**

**Moved, never rewritten.** The text below was extracted from `CLAUDE.md` §C
programmatically, not retyped, because a hand-copied law is a law with a new bug in
it (§E.8 — subtracting anything the owner specified is out of scope).

---

1. Keep the repo buildable always.
2. Never merge failing code.
3. Every discovered bug gets a permanent regression test before the fix is complete.
4. Never weaken, loosen, skip, delete, or bypass a test to make code pass — change a test only to make it STRICTER or to correct a wrong expectation, never to turn red green. (See §J.)
5. Always prove correctness on one verified case before scaling.
6. Never optimize before measuring.
7. Always verify every assumption with measurable evidence.
8. Never ship code without a rollback path.
9. Always deploy in small, reversible increments.
10. Never release changes that cannot be monitored.
11. Always fail loudly; never fail silently.
12. Never ignore warnings, failed checks, or unexpected behavior.
13. Always fix the root cause when it is known.
14. Never duplicate logic.
15. Always reuse existing systems before creating new ones.
16. Never build functionality outside the current mission.
17. Always implement the smallest complete solution first.
18. Never introduce hidden dependencies.
19. Always maintain one source of truth.
20. Never change architecture without an approved amendment.
21. Always keep modules independently replaceable.
22. Never expose secrets in code, logs, or repositories.
23. Always treat external input as untrusted.
24. Never fabricate data, metrics, logs, or results.
25. Always expose uncertainty instead of guessing.
26. Never hide trade-offs.
27. Always document irreversible decisions.
28. Never silently modify permanent documents.
29. Always leave the system better than you found it.
30. Never sacrifice correctness for speed.
31. Always optimize for readability before cleverness.
32. Never surprise future engineers.
33. Always preserve backward compatibility unless explicitly amended.
34. Never delete production data without a verified recovery plan.
35. Always verify production behavior after deployment.
36. Never allow AI-generated knowledge into canonical storage without verification.
37. Always separate AI reasoning from stored truth — reasoning changes; canonical knowledge must not.
38. Never let temporary solutions become permanent architecture.
39. Always reduce future complexity with every decision.
40. Never postpone a critical decision without recording the reason.
41. Always design systems that improve with every user interaction.
42. Never build features that don't improve user outcomes or platform capability.
43. Always make every production failure reproducible.
44. Never accept "works on my machine" as verification. **Concretely: a result exists only if GitHub CI produced it. A local pass is exploration, not evidence, and is never reported as "tested" or "verified." Every number carries its CI run URL.**
45. Always automate repetitive work once proven stable.
46. Never manually repeat work that can be safely automated.
47. Always measure system health continuously.
48. Never stop investigating until the true bottleneck is found.
49. Always remove unnecessary complexity before adding capability.
50. Never compromise long-term architecture for short-term convenience without an explicit amendment.
51. **Verify BEFORE you declare done** — the commit/ship IS the declaration. The gate PRECEDES it, never follows. A check run after you've committed is backwards. Sequence, always: **build → verify → red-team → DONE GATE → then commit.**

### 52. Nothing is built until it can be measured

Every requirement carries a **number and a unit** before work starts.

*"Fast," "better," "accurate," "soon," "a bit more," "smarter"* are **not requirements.** They are requests for a number.

**The obligation is on the engineer, not the user.** When a vague target arrives, **stop and ask for the number** before touching code. Never infer it. Never pick one yourself and proceed.

```
✗  "make it a bit faster"  →  500ms  →  495ms  →  argument
✓  "make it faster"        →  "to what number?"  →  "under 200ms"  →  build
```

A change with no measurable target has **no definition of done** and cannot be verified — which makes Laws 6, 7, 30 and 51 unenforceable.

Symmetric obligation: **never claim an improvement without before/after numbers.** *"Should be faster"* is banned exactly as *"should work"* is (§E.5).

### 53. Nature and engineering do not solve problems the same way

**Always remember: nature and engineering do not solve the same problem the same way. Think differently. Solve creatively.**

Engineering must always **transform a hard problem into an equivalent but easier-to-solve problem. Never attack the hard problem directly.**

Nature flies by flapping. Engineering flies by fixed wing plus thrust — same outcome, entirely different mechanism, vastly easier problem. **Copy the principle, never the mechanism** (§D.7).

This project already did it once. A human accountant reads a document and simply *knows* — copying that mechanism gives one model that reads and posts, and an unsolvable verification problem. The transform gave **six engines, each with a narrow checkable job.** Same outcome. Far easier problem. **Every hard thing after this gets the same treatment before anyone writes code.**

### 54. Define universally undefined concepts before building

Some terms have no definition. *Intelligence. Smartness. Information. Understanding. Correct. Safe.*

**"How do you know the AI is smart?"** You don't — and you can't — until the term has been **defined and given a number.**

**Never invent the definition yourself. Ask.** A definition chosen silently by the engineer is a decision the user never made.

```
not measurable → not provable → not true → FALSE
```

**An undefined term in a specification is a false statement waiting to be discovered.**

Standing debt in this repo — seven load-bearing undefined terms across 23 locked documents, none defined, none measurable:

| Term | Where it is load-bearing |
|---|---|
| **Confidence** | Six separate layers of it |
| **Understanding** | Engine 2's entire output |
| **Correct** | What Engine 5 validates |
| **Safe** | Validation's core question — *"is this safe to post?"* |
| **Risk** | Two separate artifacts |
| **Doubt** | Engine 3's output |
| **Uncertainty** | Travels through every engine |

These must be defined and made measurable before any build depends on them.

### 55. A mandatory gate below its threshold makes a pull request unmergeable

**There are no exceptions. Not one. Do not look for one.**

If any mandatory gate sits below its required threshold:

```
✗  do NOT recommend merge
✗  do NOT ask "should I merge?"
✗  do NOT ask for approval, an override, or an exception
✗  do NOT open a merge discussion
✓  enter FIX MODE automatically, and continue until the gate passes
```

Merge may be discussed **only** when every mandatory gate satisfies its threshold.

```
every mandatory gate passes  →  merge may be recommended
otherwise                    →  merge is IMPOSSIBLE. Fix the gate. Continue.
```

Applies to every mandatory gate that exists or ever will exist — **coverage floor ·
mutation floor · performance floor · conformance · golden dataset · adversarial tests**
— and to every one added later, automatically, without this list being updated.

**Never assume the user wants an exception.** Silence is not an override. A number close
to the floor is not the floor. A gate red "for a good reason" is red.

**Why this is a law and not a preference.** It was asked once — whether to merge at a
mutation score of 65.7% against a floor of 93. Asking was the defect. A threshold that
can be discussed is not a threshold, and the asking itself implies an exception exists.
It does not. This law removes the question, permanently.

### 56. Commit-bound measurements — a number without its commit is an opinion

**Every measurement MUST be bound to the exact Git commit that produced it. A
measurement without its commit hash is invalid.**

```
✅  Mutation: 95.3% @ commit 7e0efe2
❌  Mutation: 95.3%
```

#### Measurement lifetime

A measurement is valid **only** for the commit on which it was produced. The instant
any source code changes after that commit:

- the measurement **expires**
- it must **never** be reused
- it must **never** be quoted as current
- it must **never** be used for decision making

Instead: **re-measure**, or explicitly state **UNMEASURED**.

#### Expiration rule

Whenever code changes after a measurement, immediately state:

> Previous measurement expired because source changed after commit `<hash>`.

**Proactively. Never wait to be asked.**

#### Unknown > wrong

**Never invent continuity between commits.** If the current commit has not been
measured, write **UNMEASURED** · **NOT VERIFIED** · **PENDING GITHUB** · **PENDING CI**.

Never write the previous number. **Unknown is correct. A stale number is incorrect.**

#### GitHub is authority

Only GitHub Actions measurements are authoritative (Law 44). Local measurements are for
debugging only, and may be reported **only** when explicitly labelled
**`LOCAL ONLY — NOT AUTHORITATIVE`**. They never replace GitHub results.

#### Every number carries provenance

Every metric includes **commit hash · source · timestamp** where available:

```
Coverage : 97.54%    Commit: 7e0efe2    Source: GitHub Actions    Status: VERIFIED
Mutation : 93.41%    Commit: 7e0efe2    Source: GitHub Actions    Status: VERIFIED
```

#### Where this applies — everywhere, without exception

`ROADMAP.md` · `PROGRESS.md` · `DECISION_LOG.md` · `KNOWN_FAILURES.md` · reports ·
summaries · PR descriptions · status updates · final completion reports · chat. **No
metric may appear in documentation without its originating commit.**

#### Verification rule — run this BEFORE reporting any metric

1. Verify the commit that produced it.
2. Verify it matches the current codebase.
3. If the current HEAD differs, the metric is **EXPIRED**.
4. Re-measure, or report **UNMEASURED**.

#### Self-audit, at the end of every task

Ask: *"Does every reported metric include the commit that produced it?"* If not, correct
it **before** responding.

**A number without its commit is an opinion. A number tied to the wrong commit is false.
Only a measurement tied to the exact commit that produced it is engineering evidence.**

**Enforced in seven layers** so it cannot silently disappear: this law · the
`Commit-Bound Measurements` section of `ENGINEERING_RULES.md` · a `PreToolUse` hook that
rejects an uncited metric before the write lands · status-report format · the five
progress documents · session memory · the end-of-task self-audit.

**What forced it.** A mutation score of **95.3% @ `7e0efe2`** — real, CI-produced,
correct — stayed in a report while ~3,000 lines of source changed under it across six
modules. Nothing was wrong with the number. Everything was wrong with quoting it. The
dangerous artifact is not a red metric; it is a **green metric attached to code that has
since moved**, read by someone deciding to merge. Approved by the user, 2026-08-06.

### 57. An explicitly requested skill is a requirement, not a suggestion

When the user types a skill name — `/rtk`, `/systematic-debugging`,
`/superpowers:verification-before-completion` — that skill is **MANDATORY for
that turn**.

```
automatic routing may ADD skills    ->  always allowed
automatic routing may REPLACE one   ->  never, under any reasoning
silently dropping a requested skill ->  an ERROR, not a judgement call
```

**The failure this prevents, observed repeatedly before it was written.** Skill
names arrived appended to engineering directives and were treated as noise —
not refused, not questioned, simply never mentioned again. Silent omission is
worse than refusal, because refusal is visible and can be argued with.

**What is required of every turn carrying an explicit request:**

1. Invoke each named skill **before** planning begins.
2. If a name is not an installed skill, **say so and name it.** Never drop it.
3. If a requested skill is genuinely wrong for the work, say that in one line.
   Disagreeing out loud is permitted; going quiet is not.
4. Automatic routing runs *after*, and only ever adds.

**Priority, when they conflict:** explicit user request → project rules →
`CLAUDE.md` → engineering rules → automatic selection. Nothing downgrades the
first.

**Enforced by** `~/.claude/hooks/explicit-skill-policy.py`, a `UserPromptSubmit`
hook that parses the raw prompt for `/name` tokens and emits them as REQUIRED
before the model plans. That parse is deterministic — no model judgement stands
between the user typing a name and it arriving marked mandatory.

**The honest limit:** the hook enforces that the request is *seen*. No supported
mechanism can force the invocation, and no hook is given a record of which
skills ran, so "verify each participated" has no data source and any check
claiming to do it would be theatre. Approved by the user, 2026-08-06.

---


---

## The eight most often broken

Emitted in the session header every turn, because these are the ones measurement
showed getting skipped — not the ones that sound most important.

| Law | |
|---|---|
| **4** | Never weaken, loosen, skip, delete or bypass a test to make code pass. STRICTER only |
| **24** | Never fabricate data, metrics, logs or results |
| **44** | A result exists only if GitHub CI produced it. Local is exploration, not evidence |
| **51** | build → verify → red-team → DONE GATE → **then** commit. The gate precedes the commit |
| **52** | Nothing is built until it can be measured. A vague target is a request for a number |
| **54** | Define undefined concepts before building. Never invent the definition — ask |
| **55** | A mandatory gate below threshold makes a PR unmergeable. Do not ask. FIX MODE |
| **56** | A number without its commit is an opinion. A number on the wrong commit is false |

## Adding a law

1. Append it here with the next number. Never renumber — a law's number is cited
   across `DECISION_LOG.md`, `KNOWN_FAILURES.md` and CI code.
2. Add its entry to [`registry.json`](registry.json).
3. Update the `laws=` count above.
4. Write the §M amendment: what failure forced it, the trade-off, who approved, when.

Steps 1–3 are enforced by `tests/unit/test_engineering_os.py`. Step 4 is judgement,
and the test cannot check it — stated so nobody assumes it does.
