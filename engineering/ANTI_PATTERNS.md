# ANTI-PATTERNS

**A law says what to do. An anti-pattern says what it felt like just before it went
wrong** — which is the part that is actually recognisable in the moment.

Every entry names the measured failure that created it. An anti-pattern with no
incident behind it is a preference, and does not belong here.

---

## A · PROBLEM SELECTION

**A1 · Solving the wrong problem well**
The most expensive outcome available, because the work is real and the effort is
visible. *Cue:* the task was accepted without asking what number changes if it
succeeds. → [`METHOD.md`](METHOD.md) stage 1.

**A2 · Optimising a non-bottleneck**
Yields exactly zero and feels productive. *Cue:* "while I'm here…". *Measured:*
`max_children` was investigated as a mutation-throughput fix; it already defaulted to
`os.cpu_count()`, so parallelism was maximal and the work was worth nothing.

**A3 · Attacking the hard problem directly**
*Cue:* the plan's first step is the hardest step. Transform it into an easier
equivalent problem first (Law 53).

**A4 · Automating before deleting**
Question → Delete → Simplify → Accelerate → Automate. Out of order, you make the wrong
thing cheaper to keep.

---

## B · EVIDENCE

**B1 · Treating a document as evidence**
*Measured 2026-08-06:* two of three testable claims in `KNOWN_FAILURES.md` were FALSE.
One became root cause "R4", which died the moment the code was read — the pipeline had
no PDF special case at all. **A document is a hypothesis. Read the source.**

**B2 · Publishing an unverifiable metric**
A score with no falsifier is an opinion wearing a number.

**B3 · A score without a complete denominator**
*Measured:* 919 of 3358 mutants — 27.4% — sat outside the denominator, unreported. A
gate looks healthier as it degrades.

**B4 · Quoting a number from a different commit**
*Measured:* mutation 95.3% @ `7e0efe2` stayed in a report while ~3,000 lines changed
under it. Nothing was wrong with the number; everything was wrong with quoting it.

**B5 · Reporting a local pass as a result**
Law 44. Local is exploration. *Measured:* pip silently downgraded numpy locally with
no error, while CI refused outright. Only CI told the truth.

**B6 · Confirmation-only verification**
Going looking for evidence you are right. Go find the disconfirming kind, specifically.

**B7 · Hedging in a truth document**
*"probably" · "I think" · "should work"* in `KNOWN_FAILURES.md`, `PROGRESS.md`,
`STATE.md`, `BLOCKERS.md`. Blocked by a hook. Write MEASURED or write UNKNOWN.

---

## C · REQUIREMENTS

**C1 · An adjective with no number**
fast · better · reliable · scalable · clean · robust. No definition of done → nothing
to verify.

**C2 · Building on an undefined term**
Law 54. Seven load-bearing undefined terms were carried across 23 locked documents
before this was caught.

**C3 · Inventing the definition or the threshold yourself**
A decision the owner never made, wearing the engineer's confidence. Ask.

**C4 · Designing from the solution**
HOW → WHY instead of WHY → WHAT → HOW. The requirements get chosen silently by the
design, and nobody sees which ones were rejected.

**C5 · An orphan**
An implementation with no requirement above it is unscoped work. A requirement with no
test below it is an opinion.

---

## D · TESTS

**D1 · Weakening a test to make code pass**
Law 4. Only ever stricter. No exceptions, no "temporarily".

**D2 · A test that passed first try**
It never failed, so it has never demonstrated it can. Watch it RED for the right
reason first.

**D3 · Asserting that a function ran**
*"Didn't throw"* and *"returned something"* prove nothing. Name the outcome, assert
THAT.

**D4 · Testing the mock**
A mock proves the mock. Fake only at the narrowest I/O edge. Parsing and validating
untrusted input is LOGIC — test it for real, with hostile input.

**D5 · A test shaped by the signature it is testing**
*Measured:* `cleaner` had 61 tests and every one fed it an image, because that is what
`decode` accepted. **A test suite shaped by the signature can never question the
signature.** Only wiring the chain asked the question.

**D6 · Asserting on the wrong quantity**
*Measured:* F-028's own test asserted page size in points, so it could not see the
663× file-size regression the fix introduced. **A test can only fail on what it looks
at.**

**D7 · Gate-green mistaken for product-works**
A typecheck-lint-unit gate never loads the app.

---

## E · CHANGE

**E1 · Committing before the gate**
Law 51. The commit IS the declaration of done. A check after it is backwards.

**E2 · Asking whether to merge below a threshold**
Law 55. The asking is the defect — it implies an exception exists. Enter FIX MODE.

**E3 · Fixing a symptom and calling it a root cause**
Stopping at an explanation. An identified cause is not an eliminated one.

**E4 · Re-opening a disproved hypothesis without new evidence**
Costs a full cycle every time.

**E5 · Two changes in one**
A correctness fix plus a contract migration makes failures unattributable.

**E6 · Silently narrowing scope**
Compressing 40 findings into 9 without saying so. Report what you changed, exactly —
a change the owner has to discover is a change made without consent.

**E7 · Removing something the owner specified**
§E.8. Adding rigour is in scope. Subtracting anything is not, even when it is
defensible on cost or complexity grounds. The owner pays and owns the trade-off.

**E8 · Serial work on independent problems**
A defect, not a style. Dispatch concurrently.

---

## F · SYSTEM

**F1 · Duplicating a rule**
*Measured:* test discipline existed in two files, Law 51 in four places, the mission in
three, and the law count in one of them was stale by two. **Fixing one copy leaves the
others lying.** One rule, one home, links everywhere else.

**F2 · A mandatory document too long to apply**
*Measured:* 951 lines with a header ordering a full re-read every time, and a §N in
the same file explaining that this cannot work. Attention is the constraint, not
tokens.

**F3 · Enforcing at load time and never at output time**
A rule that is emitted but never checked against what was produced is a rule with no
evidence it was applied.

**F4 · A count that drifts**
"55 laws" beside 57 laws teaches the reader the document is unreliable, and an
unreliable document stops being consulted.

**F5 · Enforcement that lives outside the repository**
*Measured:* `git ls-files .claude/` returned nothing. Every hook enforcing this
project's rules lived in one laptop's home directory. A fresh clone got zero
enforcement.

**F6 · A guard nobody watched refuse**
Unproven. Observe it blocking, then observe it permitting the legitimate case — a
check that refuses everything is removed within a day.

---

## HOW TO ADD ONE

Name the incident, the measurement, and the recognisable cue. **No incident, no
entry** — this file is a record of what actually went wrong, not a list of things that
sound unwise.
