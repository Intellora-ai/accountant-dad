# ENGINEERING_RULES.md

> **Pointer, not a copy.** The rules live in [`CLAUDE.md`](CLAUDE.md) — §C the 55 laws,
> §D how to think, §E how to work, §I the build→verify→fix loop, §J test discipline,
> §N the DONE GATE. That file is the constitution and outranks this one.

## Test discipline — §J, the ten that matter most

**Goal: NO FALSE GREEN.** A passing test must mean the real production path works.

Two traps kill this, and both have bitten this repository:

1. **Gate-green ≠ product-works.** A typecheck-lint-unit gate never loads the app.
2. **You write the test and the code with the same blind spots**, so the test confirms
   your assumptions instead of attacking them.

```
1   Test first — watch it FAIL for the right reason. Passed first try = wrong test
2   Assert the real RESULT, not that a function ran. "Didn't throw" proves nothing
3   Cover success AND failure: empty, boundary, the exact bug
4   NEVER ease a test. Code fails a correct test → fix the CODE
5   Break it on purpose — mutate, confirm red. Run against the REAL dependency
6   REAL + ISOLATED. A mock proves the mock
7   Fake only at the narrowest I/O edge. Parsing and validating untrusted input is LOGIC
8   Every bug → a permanent test that fails before the fix and guards it forever
9   Extract the problem PRINCIPLE so the whole class cannot recur
10  Red-team + falsify before "done". Green is not done. Survived-an-attack is done
```

## The sequence — Law 51

```
build → verify → red-team → DONE GATE → THEN commit
```

The gate runs **before** the commit, never after. A commit IS a declaration of done.

## Measured, not asserted

Every number carries its units and its provenance. Every claim of improvement carries
before/after. *"Should be faster"* is banned exactly as *"should work"* is.

---

## Commit-Bound Measurements — Law 56

**This is the canonical rulebook entry. The law is `CLAUDE.md` §C.56; this is how it is
applied in practice.**

### The rule

**A measurement is bound to the exact commit that produced it. Without that commit hash,
it is invalid.**

```
✅  Mutation: 95.3% @ commit 7e0efe2
❌  Mutation: 95.3%
```

### Lifetime — a measurement expires the moment source changes

A measurement is valid **only** for its commit. The instant any source changes after it:

| | |
|---|---|
| reused | **never** |
| quoted as current | **never** |
| used for a decision | **never** |

The only two valid responses are **re-measure** or **UNMEASURED**.

### Say it before you are asked

When code lands after a measurement, state it immediately, in the same message:

> Previous measurement expired because source changed after commit `<hash>`.

### Unknown beats wrong

Never invent continuity between commits. If HEAD is unmeasured, write one of:

```
UNMEASURED · NOT VERIFIED · PENDING GITHUB · PENDING CI
```

**Never** the previous number. Unknown is correct; a stale number is incorrect.

### Authority

Only GitHub Actions is authoritative (Law 44). A local run may be reported **only** when
labelled **`LOCAL ONLY — NOT AUTHORITATIVE`**, and never as a substitute.

### The reporting format

```
Mutation
93.42%
Commit: 7e0efe2
Source: GitHub Actions
Status: VERIFIED
```

Every metric: **value · commit · source · status**, plus a timestamp where one exists.

### Verification, before reporting anything

1. Which commit produced it?
2. Does that commit match the current codebase?
3. If HEAD differs → **EXPIRED**.
4. Re-measure, or report **UNMEASURED**.

### Where it binds

`ROADMAP.md` · `PROGRESS.md` · `DECISION_LOG.md` · `KNOWN_FAILURES.md` · `STATE.md` ·
reports · summaries · PR descriptions · status updates · completion reports · chat.

**No metric appears in any of them without its originating commit.**

### Scheduling consequence, and it is not a footnote

Re-measuring the mutation gate costs **~3.4 hours**. So expensive gates — mutation, the
coverage ratchet, benchmarks — are **batched to the end of a change set** and paid once.
Cheap gates — lint, typecheck, tests — re-run freely after every change. That sequencing
is decided **before** the changes land, not after.

### Enforcement — seven layers, so it cannot quietly lapse

| Layer | Where |
|---|---|
| 1 | `CLAUDE.md` §C Law 56 — the constitution |
| 2 | this section — the canonical rulebook |
| 3 | `PreToolUse` hook — rejects an uncited metric **before** the write lands |
| 4 | status-report format — value · commit · source · status |
| 5 | the five progress documents — no uncited metric, ever |
| 6 | session memory — inherited by every future session |
| 7 | end-of-task self-audit — `§N` DONE GATE item 12 |

**A number without its commit is an opinion. A number tied to the wrong commit is false.**

**Full text:** [`CLAUDE.md`](CLAUDE.md)
