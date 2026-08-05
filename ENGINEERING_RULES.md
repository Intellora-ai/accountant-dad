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

**Full text:** [`CLAUDE.md`](CLAUDE.md)
