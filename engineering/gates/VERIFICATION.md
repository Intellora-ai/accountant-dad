# GATE · VERIFICATION

**Fires when:** writing or changing a test, and **before every commit** — a commit IS
a declaration of done (Law 51). Also before any claim that something works.

**GOAL: NO FALSE GREEN.** A passing test must mean the REAL production path works.

Two traps kill this, and both have bitten this repository:

1. **Gate-green is not product-works.** A typecheck-lint-unit gate never loads the app.
2. **You write the test and the code with the same blind spots**, so the test confirms
   your assumptions instead of attacking them.

---

## THE SEQUENCE — Law 51, and it is not negotiable

```
build  ->  verify  ->  red-team  ->  DONE GATE  ->  THEN commit
```

**The gate runs BEFORE the commit, never after.** A check run after committing is
backwards, because the commit already declared the thing done.

---

### BUILD

1. **One phase at a time** — finish fully, then commit.
2. **Reuse before building** — don't rebuild what exists (Law 15).
3. **Delete before you add** — fewer lines = fewer bugs; the best code is removed code.
4. **Make it work → make it right → make it fast**, in that order (Law 6).
5. **If a change is hard, reshape the code first, then make the easy change** (Law 53 applied to code — transform the hard problem).
6. **Build small single-purpose pieces**, not one giant block.

### VERIFY

7. **CI auto-runs every test on every change** — red = can't merge. The green gate is mandatory, not willpower.
8. **Write the test first, watch it fail, build until it passes, then clean up.** A test that never failed tests nothing.
9. **Break things on purpose** — inject a fake, prove it is rejected.
10. **FALSIFY + RED-TEAM before green** (§D.13, §J.10). Don't confirm your code works — try to **PROVE it WRONG**. Attack it through the real pipeline with hostile and edge input. On anything non-trivial, run a **separate adversarial pass** — a different stance finds what yours can't. **Green is not done. Survived-an-attack is done.**

### FIX

11. **A red error stops everything.** Don't build on broken.
12. **Ask Why until you hit the FUNDAMENTAL cause.** "5 Whys" is a mindset, not a count — some causes are 5 deep, some 12. Stop only at the true root. **If the root is a whole CLASS, fix the class**, not the instance.
13. **Every bug becomes a permanent test** — reproduce it, write a failing test that traps it, fix the cause, the test guards it forever (Laws 3, 4).
14. **SEQUENCE (Law 51):** loop until green → run the DONE GATE (§N) → **THEN** commit → next phase. **The gate runs BEFORE the commit, never after.** Committing before verifying is declaring done before it is done.

---


---

**Goal: NO FALSE GREEN — a passing test must mean the REAL production path actually works.**

Two traps kill this:
- **(a) gate-green ≠ product-works.** A typecheck-lint-unit gate never loads the app. Before "done," exercise the real running system.
- **(b) You write the test and the code with the same blind spots**, so the test confirms your assumptions instead of attacking them. Write every test to **BREAK** the code, and red-team non-trivial work with a separate pass.

1. **Test first** — write it, watch it FAIL for the right reason, then make it pass. **Passed first try = wrong test.**
2. **Assert the real RESULT, not that a function ran.** Name the outcome first, assert THAT. *"Didn't throw / returned something"* proves nothing.
3. **Hard** — cover success AND failure/edge: empty, boundary, the exact bug. **A test that cannot fail isn't done.**
4. **Never ease a test** — no loosening, deleting, skipping, mocking-away, lowering a floor. Code fails a correct test → **fix the CODE**. Only make tests STRICTER (Law 4).
5. **Break it on purpose** — mutate the code, confirm the test goes red. Run against the REAL dependency, not a stand-in.
6. **REAL + ISOLATED** — exercise the exact production dependency (a mock proves the mock). Each test in its own disposable environment. Destructive operations guarded against non-test targets **by construction, not by care.**
7. **Fake only at the I/O edge** — stub the narrowest external call (HTTP / DB / clock). Parsing, validating and mapping untrusted input is **LOGIC** — test it for real with hostile input.
8. **Every bug → a permanent hard test** that fails before the fix and guards it forever.
9. **Extract the problem principle** — name the general root cause so the whole CLASS cannot recur, not just patch the instance.
10. **Red-team + falsify before "done"** — try to prove your code AND your tests WRONG (inversion, hostile input, real wiring). **State which CLAUDE.md rules you verified.** A rule loaded is not a rule applied.

---


---

## VERIFICATION METHODS — name one, or the requirement is invalid

Every requirement states how it will be proven. Only four are allowed:

| Method | Use when |
|---|---|
| **Inspection** | the property is visible in the artifact — a pin, a type, a licence |
| **Analysis** | it follows from something already proven, by stated reasoning |
| **Demonstration** | running it once, observably, shows the behaviour |
| **Test** | an automated, repeatable assertion that can fail |

**If no method can be named, the requirement is not verifiable and must be rewritten**
(see [`REQUIREMENTS.md`](REQUIREMENTS.md)).

---

### HOW THIS FILE IS APPLIED — read this, it is why rules get skipped

CLAUDE.md is a large REFERENCE document, but universal application needs a **SMALL checklist fired at a FIXED TRIGGER.** A long document cannot be re-run from finite attention at every step, so compliance drifts to *"apply what's salient"* — and ship, monitor, laws and wiring-tests all slip the same way.

The fix has two layers:

1. **Automate every rule that CAN be a gate** — CI (can't-merge-red), lint, tests, guards. Unskippable, needs no attention. **Prefer converting a judgment rule into an automated gate whenever possible.**
2. **For judgment rules that cannot be automated** — run the DONE GATE below: a compressed, **STATED** checklist at fixed triggers. **Stating each line is the forcing function** — a silent skip becomes a visible blank you must confront.

### THE DONE GATE

Do this before **EVERY** "done," no exceptions. **A COMMIT or SHIP IS a "done," so the gate runs BEFORE `git commit`, never after (Law 51).**

A rule loaded in this file is *available*, not *applied*. Before declaring any change or phase done you MUST **OUTPUT an explicit COMPLIANCE PASS** that walks the whole constitution — not just tests, not just mental models. Writing it is the gate. A silent "done" is forbidden.

For each, mark ✓ (did it) or N/A (why it doesn't apply):

- **§C Laws** — name the ones this change touches; confirm none broken. Especially: buildable · root-cause · one source of truth · no secrets · **never fabricate** · **everything measurable (52)** · **problem transformed, not attacked (53)** · **no undefined terms (54)**.
- **§D thinking** — which models you actually applied: First Principles, Inversion, Simplicity, Trade-offs, Second-Order, **Falsification**, **Problem Transformation**. Applied, not named.
- **§E how to work** — repository-is-reality (read the real code) · decided vs asked correctly · verified empirically · one task, no scope creep.
- **§F/G/H method** — under the frozen architecture, no silent shape change · blueprint updated to match reality (Law 19).
- **§I build→verify→fix + §J all 10 test rules** — test-first · hard · never-eased · mutation-proven · bug→permanent test · REAL+ISOLATED · fake-at-I/O-boundary · problem-principle extracted · red-teamed.
- **§K ship / §L monitor** — flag off + rollback (if shipping) · signals (if live).
- **§M amend** — if a frozen doc was touched, the amendment is written.
- **§O** — pointers and docs updated.

Then the 10 gates:

1. Tests written — success AND failure cases
2. Typecheck · lint · tests · build all green
3. No earlier test weakened
4. Verification shown with **real output**
5. Rollback exists
6. Monitoring ready
7. Docs updated
8. The mission goal is achieved
9. **Red-teamed + falsified** (§J.10) — you actively tried to prove the change AND its tests WRONG, not just watched green. State which rules you verified.
10. **Every number in the change is measured, not estimated** (Law 52). No "should be faster." Before and after, with units.
11. **Every mandatory gate is AT or ABOVE its threshold** (Law 55). Not close to it. If one is below, this change is not done, merge is not discussable, and the only valid next action is fixing that gate.
12. **Every metric carries the commit that produced it** (Law 56). Run the self-audit: does every number reported here name its commit, its source, and its status? A metric measured before the current HEAD is **EXPIRED** — re-measure or write **UNMEASURED**. Never quote the previous number.

**If any line cannot be ticked, it is NOT done.**

---

---

## CHECKLIST — state every line, ✓ or N/A with the reason

- [ ] Test written FIRST, watched RED, for the RIGHT reason
- [ ] Success AND failure cases: empty, boundary, the exact bug
- [ ] The real RESULT asserted — not that a function ran, not that it did not throw
- [ ] The right QUANTITY asserted (a test only fails on what it looks at)
- [ ] No earlier test weakened, loosened, skipped or mocked away (Law 4)
- [ ] Run against the REAL dependency; faked only at the narrowest I/O edge
- [ ] Mutated on purpose and confirmed RED
- [ ] Every bug has a permanent test that fails before its fix
- [ ] The class-level PRINCIPLE extracted, not just the instance patched
- [ ] Red-teamed: I tried to prove the code AND the tests WRONG
- [ ] Typecheck · lint · tests · build all green, with real output shown
- [ ] Every number measured, not estimated, with its unit and its commit
- [ ] Every mandatory gate AT or ABOVE its threshold (Law 55) — else FIX MODE
- [ ] Rollback exists · monitoring ready · docs updated
- [ ] Ran BEFORE the commit, not after (Law 51)

**If any line cannot be ticked, it is NOT done.**
