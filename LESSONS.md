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
## L-014 · A reference is not a check, and three failures were the same sentence

**Cost:** one repository that would not build, 1712 lines of tests that could not run, and
three finished sub-engines that never saw a document.

F-018, F-024 and F-025 were filed as three unrelated defects. They are one sentence with
three different objects:

```
F-024   a NAME is imported          and nothing defines it
F-025   a CALL is written           and the callee's parameters have moved
F-018   a MODULE is built           and nothing imports it
```

Every one is a reference that was never checked against the thing it refers to. Every one
was found by a human running something expensive, long after it landed.

**Why the existing gates could not see any of them.** They all ask about a component in
isolation. `unit tests` imports a module directly and proves it works. `coverage` counts
the lines those tests executed. `mutation` confirms those tests kill mutants. All three go
green on a module nothing calls, a call site that no longer binds, and a name whose only
definition is a docstring paragraph. **Nothing in the repository compared a reference to
its referent.**

The one thing that would have caught F-024 and F-025 — running the suite — is the thing
F-024 had broken. A collection error is not one red test; it is **zero results**, and it
takes every downstream gate with it.

**Rule.** A reference is a claim, and an unchecked claim is not a check. Every kind of
cross-file reference this repository makes gets a mechanical validator that resolves it:
imports against definitions, calls against signatures, modules against the import graph.
They are static, they run in under a second, and they name every offender at once — where
the runtime equivalents take 245 seconds, report only the first failure, and cannot run at
all when the thing they would report is what is broken.

**The corollary, and it is the part that keeps being paid for.** Fixing the instance is not
fixing the class (§I.12). `Exclusion` was written, `recorded_at` was passed, and both
symptoms went green while the mechanism that produced them stayed exactly as it was.
`tools/ci/unresolved_symbols.py`, `tools/ci/signature_drift.py` and
`tools/ci/module_wiring.py` are what changed.

**A validator that reads source must read AUTHORED source (L-006).** All three go through
`tools/ci/authored_source.py`. `signature_drift` is the sharp case: under `mutmut run` the
live function is a generated dispatcher taking `(*args, **kwargs)`, which binds every call
— so an `inspect.signature`-based version would report green on a tree full of stale call
sites at precisely the moment the tree is most rewritten. That is the silent direction of
L-006, and it costs a whole gate run to discover.

**Conservative beats clever, in one direction only.** Where a validator cannot resolve a
reference with certainty — an unpacked `*args`, a rebound name — it declines and says so,
rather than guessing. A missed check is a gap; a WRONG check is a false alarm on correct
code, and a gate that cries wolf is a gate somebody eventually weakens (§J.4).

---

## L-015 · Replacing a library call replaces its DEFAULTS, and defaults are behaviour

**Cost: a 663x file-size regression, written, reviewed by me, committed and pushed.**

Fixing F-028 meant replacing `image.convert_to_pdf()` with `new_page` +
`insert_image`. The geometry fix was right, measured across five DPIs, and falsified
before it was trusted. It shipped anyway with a defect that made every rebuilt scan
**663x larger at 150 dpi and 905x at 300**:

| dpi | default save | `deflate=True` | old `convert_to_pdf` |
|---|---|---|---|
| 150 | 6,314,818 B | 9,517 B | 9,479 B |
| 300 | 25,248,570 B | 27,915 B | 27,873 B |

`convert_to_pdf()` returned an already-compressed document, so the old code never had
to ask for compression and no line anywhere in the repository mentioned it. The
replacement writes an image object that is Flate-compressed only when the document is
**saved**, and the default save does not. **The old call was carrying a decision
nobody had written down.**

**THE PRINCIPLE.** When a fix swaps a library call for a hand-built equivalent, the
old call's defaults were behaviour the code depended on and never stated. Every one of
them is now yours, unstated and unasserted. Before swapping, ask what the old call did
that no line of code asks for — compression, ordering, encoding, buffering, cleanup —
and assert each of those separately.

**WHY THE FIX'S OWN TEST DID NOT CATCH IT, WHICH IS THE SHARPER HALF.** The F-028 test
asserts the rebuilt page's size in POINTS. The geometry was correct in both worlds.
The bytes were wrong; the coordinates were not.

**A test can only fail on what it looks at.** A test written for a fix tends to look
at exactly the property the fix was about, so it is structurally blind to whatever
else the fix changed. The question to ask after every fix is not *"does my test pass?"*
but *"what else did this change, and what looks at THAT?"*

**Guarded by** `test_a_rebuilt_page_stores_its_image_compressed_not_raw`, whose bound
is derived rather than chosen: the size the page's own pixels would occupy
uncompressed, `width x height x channels`. "Smaller than raw" is exactly what "stored
compressed" means, so it needs no invented threshold and no tolerance (Law 10).

---

## L-016 · One sample reported as a property is a red gate waiting to happen

**Cost: `coverage` red on CI, blocking every gate behind it, for a defect that was
never in the code under test.**

`KNOWN_FAILURES.md` recorded a real finding precisely: two cleans of one scan produce
*"two payloads of identical length — 5465 bytes — differing in exactly 58 of them."*
Every number in that sentence was true of the run that produced it. A test was written
to pin it, asserting equal payload length.

It failed on CI:

```
AssertionError: assert 5457 == 5465
```

Re-measured over 3000 saves, the "identical length" half was simply false:

```
/ID span (bytes)   66  67  68  69  70  71  72  73
occurrences         2   2   1   1   4   1  19  2969
```

A PDF byte string has two legal serialisations, and PyMuPDF chooses per save over
bytes that are **random by construction**. The assertion compared a random variable to
itself. Measured failure rate: 14 in 400 pairs.

**THE PRINCIPLE.** *N=1 tells you a value. It does not tell you a property.* Before an
observation becomes an assertion, ask what would make it vary and sample it enough
times to see. The cost of not asking is the worst kind of red: rare enough to read as
flakiness, frequent enough to block a mandatory gate, and pointing at innocent code.

**The corollary that made it worse.** The same test then asserted only that differing
bytes fall after the `trailer` keyword — but `trailer` is followed by `/Size`, `/Root`
and `/ID`, so a changed root object would have passed as identifier noise. **A test can
be simultaneously too strict about the wrong thing and too loose about the right one.**

**The replacement** excises the `/ID` array and asserts everything else is byte for
byte identical: no dependence on a random length, and strictly less permitted
variation. Measured: 1 distinct remainder in 300 cleans, 0 failures in 400 pairs.

---

## L-017 · A failure artifact that carries real data will pass a test written for real data

**Cost: the test proving Engine 1's ROADMAP completion criterion was GREEN against a
document that never reached the parser.**

CI printed `.F` — a pass, then a fail. Attention went to the F. The pass was the
defect.

`pipeline._stopped` classifies a parser failure as a BUSINESS failure, so `run` returns
an artifact recording it rather than raising. That artifact is deliberately rich: it
carries `reader`'s **real extracted text**, because the design is that a failure is
routed rather than crashed. The end-to-end test asserted
`extracted_text == "\n".join(ALL_LINES)` — and a failure record satisfies it exactly.

**THE PRINCIPLE.** A well-designed failure object is built to look as much like a
success as it honestly can, so downstream code can keep working. That is correct
design, and it means **a test asserting on the payload cannot tell the two apart.**
Any test that means "this succeeded" must assert on something only success produces,
never on content that both paths populate.

**The second lesson is about diagnosis.** The parser's real reason was already on the
artifact — Docling's own `result.errors`, reaching `reliability_information` and the
uncertainty marker through `parser.py:750`. Nothing read them, so CI could only say
which stage failed and never why, and three separate hypotheses were investigated and
refuted to recover information the system already had. **When a failure is hard to
diagnose, check whether the diagnosis is already being produced and discarded before
building anything new to find it.**
