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

---

## L-011 · A measured number belongs to the commit that produced it

The mutation gate read **95.3% on `7e0efe2`** — killed 2324, survived 115, floor 93. Real,
CI-produced, and correct. Within the next few hours roughly **3,000 lines of source**
changed across `cleaner.py`, `classification.py`, `measurement.py`, `config.py`,
`confidence_report.py` and `pyproject.toml`.

That score did not survive any of it. Not because it was wrong — because it was measured
on a tree that no longer exists.

The dangerous shape is not a red number. It is a **green number attached to code that has
since moved**, sitting in a report, read by someone deciding to merge. Law 44 says a result
exists only if CI produced it; the corollary is that it exists only **for the tree CI ran
on**. Law 52's *"never claim an improvement without before/after numbers"* fails identically
when the "after" is stale.

**Rule.** Every number carries its commit — `95.3% on 7e0efe2`, never `95.3%`. When source
lands after a measurement, say the number has expired **in the same message, unprompted**,
before anyone can act on it. Never carry a figure forward across a source change; re-measure
or call it unmeasured, and an unmeasured gate is not a passing gate.

**The corollary that costs real time.** Re-measuring mutation is **~3.4 hours**. That is not
a footnote, it is a scheduling constraint: expensive gates get **batched to the end of a
change set** so the cost is paid once instead of per commit, while cheap ones — lint,
typecheck, tests — re-run freely after every change. Sequencing work to measure once is a
design decision, and it has to be made before the changes land, not after.

Applies to documents too. A number written into `ROADMAP.md` or `PROGRESS.md` without its
commit is a claim nobody can check.

**Owner's standing instruction, 2026-08-06:** do this every time anything changes.

---

## L-012 · Land a whole stack or none of it

An agent was killed mid-task. Its `parser.py` work sat in commit `e902ab4`, and I judged
it unfinished and deliberately did not land it. A second agent resumed **from that
commit**, and produced three more on top of it. I cherry-picked those three.

Result: **42 failed, 45 errors**, up from 2.

```
59×  TypeError: run() missing 1 required keyword-only argument: 'recorded_at'
14×  AttributeError: module 'parser' has no attribute 'ExtractedRegion' / 'MappedField'
```

The `pipeline.py` I landed called a `parser.py` API I had withheld. Half a change set.
It imported cleanly, typechecked cleanly, and failed at runtime — because the missing
half was a *sibling module*, not a syntax error.

Then I made it worse: the replay hit merge conflicts and I resolved them with a blanket
`git checkout --theirs`. That is the same shortcut a second time, and it **hides which
half is missing** — the conflict was the one signal that the stack was incomplete, and I
silenced it.

**Rule.** When an agent's work arrives as a stack of commits, land the **whole stack or
none of it**. A judgement that the top commit is "unfinished" does not license taking the
commits above it — they were written against it. And never resolve a cherry-pick conflict
mechanically: a conflict on a file two agents both touched is information, and `--theirs`
throws it away.

**The recovery that worked:** reset to the last known-good commit and replay the stack in
dependency order, base first. Zero conflicts, because the order was right.

Related: **L-007** — integration finds what unit tests structurally cannot. This is the
same shape one level up: nothing in a unit test can see that a *neighbouring module's*
half of a change never landed.

---

## L-013 — A test that reads source is reading the *interpreter*, not the repository

**Cost: the `mutation` gate scored nothing for eight commits, and nine architecture
guards were silently switched off inside it.**

The gate did not run long and fail. It died in six minutes reporting `4075 not
checked`, which reads exactly like an unbuilt placeholder and is not one. mutmut runs
the whole suite ONCE to collect stats before the first mutant; one red test there
aborts the run, and every mutant is reported unscored.

The red test:

```
FAILED tests/unit/test_input_engine_assembly_redteam.py::
       test_assembly_compares_only_against_none
AssertionError: assembly compares against something other than None:
  [(136, ["Constant(value='fail')"]), (139, ["Constant(value='stats')"])]
failed to collect stats. runner returned 1
```

Lines 136 and 139 are **mutmut's own dispatcher**, injected into every module it
mutates. Pristine `assembly.py` contains zero occurrences of either literal. The
test asked a question about the repository and `inspect.getsource` answered a
different question: *what is this interpreter running.*

**The silent direction is worse.** mutmut renames every function — `run` becomes
`x_run__mutmut_orig` and the public name becomes the dispatcher — so
`inspect.getsource(module.run)` returns eight lines of boilerplate. An assertion like
"`run` never calls `min()`" then PASSES against mutmut's code. A red gate gets
investigated; a green one does not.

**What made it expensive was the response, not the bug.** This class had been hit and
patched **seven times**, each with a runtime `pytest.skip` under mutation. Every patch
was locally reasonable and globally wrong: nine structural red-team guards — the ones
pinning Engine 1's architecture — stopped running in the one job that scores Engine 1,
and the gate went on reporting a number with them disabled.

**Rule.** *Authored source is a property of the repository, not of the process.* Any
test asserting about source reads it from the authored file, through
`tools/ci/authored_source.py`. When a test must instead see what is LOADED — `runpy
.run_path` on a CLI entry point, where executing the authored file would leave every
mutant in it alive and undetected — it says so with `running_path`. The choice is
never made by reaching for `__file__`.

**On finding all of it at once.** CI runs with `-x`, so it showed one failure. Fixing
that one would have cost another six-minute round to find the next. Reproducing the
instrumented tree locally and running both trees WITHOUT `-x` gave the whole list in
one pass: **4 hard failures and 9 silent skips**, not 1. When a slow gate fails, make
the cheap version of its environment first and read the full failure set.

**On the guard.** The validator's first version banned only
`Path(x.__file__).read_text()` and was defeated within the hour by
`top_level_imports(reader.__file__)` — the read and the `__file__` in different
functions. Connecting those needs dataflow analysis; banning the attribute needs none.
**A guard scoped to the instance you just fixed is not a guard.** It then caught a
brand-new offending call site the same afternoon, in an agent's work, before it landed.

Related: **L-011** — measured numbers expire when source changes. The two compound:
a stale number attached to a gate that was not measuring is the worst artifact in the
repository.
