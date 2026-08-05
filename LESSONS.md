# LESSONS.md

What this project learned the expensive way. Append only — a lesson deleted is a lesson
about to be re-learned.

---

## L-001 · A green suite proves nothing until you check which libraries loaded

**Cost:** a reported "2068 passed" that was withdrawn, and hours built on it.

`requirements-engine1.txt` pinned `numpy==2.5.1` and `opencv-python==5.0.0.93`. The
process was actually running `numpy 2.3.5` and `cv2 4.10.0` — pip had silently
downgraded one and a transitive `opencv-contrib-python` had shadowed the other. No error,
no warning. The suite was green against libraries nobody chose.

**Rule:** after any install, `import` the pinned packages and print their versions. A
manifest states an intention; only the interpreter states a fact.

---

## L-002 · A dry-run resolving cleanly is not evidence

PaddleOCR's `pip install --dry-run` resolved fine, then silently replaced two pinned
libraries. Docling's dry-run also resolved fine — and was genuinely safe, verified by
reading versions back afterwards.

**Rule:** the dry-run tells you pip *can* solve it, never what you'll end up with.

---

## L-003 · `pytest.raises(X)` with no `match=` is barely a test

Seven mutation survivors sat in one nine-line function because its test asserted only
that *something* raised. Mutations to the message, to `sorted()`, to the set
comprehension, and to `count(name) > 1` all still raised — so all seven survived.

**Rule:** `pytest.raises` always carries `match=`, or asserts on the message afterwards.
§J.2 — assert the RESULT, not that a function ran.

---

## L-004 · macOS cannot run mutation testing at all

mutmut calls `set_start_method('fork')`. On macOS, `fork()` after OpenCV, torch or
Accelerate have initialised leaves the child with broken thread state — SIGSEGV before a
single test runs. **2133/2133 mutants segfaulted; zero usable data.**

**Rule:** for mutation, Law 44 is not policy, it is hardware. Every hypothesis costs a
full CI run (~3 hours at this scale). Guess carefully, and batch the fixes.

---

## L-005 · Scoping `paths_to_mutate` breaks the mutants tree

Two dead ends, both paid for:

- Narrowing `paths_to_mutate` makes mutmut copy **only** that path → sibling imports die
  → `failed to collect stats`.
- "Fixing" that with `also_copy = ["src"]` copies the **unmutated** source over the
  mutated tree → `FAILED: Unable to force test failures`, correctly, because no test
  could ever see a mutant.

**Rule:** copy each sibling path individually, never the mutation target.

---

## L-006 · A test that reads its own source breaks under mutation

Five tests used `inspect.getsource` / `read_text` on the module under test and asserted
structure. Under mutmut that source is mutmut's rewrite, not ours — so the whole baseline
failed and **3157 mutants scored as "not checked"**: a gate reporting nothing while
looking like it ran.

**Rule:** any test that parses its own source must detect instrumentation
(`"__mutmut_" in source`) and skip, saying why.

---

## L-007 · Integration finds what unit tests structurally cannot

Every Engine 1 module passed its own tests. Wiring them into one pipeline immediately
exposed four defects — including `cleaner.decode` being **unable to decode a PDF at all**,
the MVP's primary input, missed by 57 cleaner tests because every one of them feeds it an
image.

**Rule:** "all modules green" is not "the engine works". Build the chain early; it is a
different kind of test, not a bigger one.

---

## L-008 · macOS Finder duplicates get committed and go stale

Three found in one day: `ENGINE_1_CONFIDENCE_PARAMETERS 2.md` (which still carried an
inverted row the original had corrected), `EVIDENCE_ARCHITECTURE 2.md`, and
`config 2.py` / `measurement 2.py` staged by `git add -A`.

**Rule:** before `git add -A`, check `git status` for names ending ` 2`. A stale
duplicate of a sign-off document is worse than no document.

---

## L-009 · A cancelled gate hides its own verdict

The mutation gate was assumed to be failing on score. It was being **cancelled** — and
when finally given time, it reported **92.7% against a floor of 93**. Both problems were
real; the timeout was masking the second.

**Rule:** a job that cannot finish has no verdict. Fix the ability to report before
interpreting the report.

---

## L-010 · Optimising the wrong thing costs correctness

`_bands_for` rebuilds the Table Transformer once per table — 1.68 s per call, measured.
Caching it was implemented **twice** and reverted both times: as module-level Protocols
it cost 0.057pp of coverage, and under `TYPE_CHECKING` it cost 0.66pp because the classes
then never execute. It also would not have helped the mutation clock — each mutant is a
fresh process.

**Rule:** confirm the fix addresses the actual constraint before paying for it. Recorded
as F-015 and left undone deliberately.
