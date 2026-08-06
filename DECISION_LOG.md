# DECISION_LOG.md

Every architectural decision, with what it cost. **Append only. History is never
overwritten** — a decision that turns out wrong gets a new entry that supersedes it,
and the original stays.

A decision belongs here when it is hard to reverse, when it closes off options, or
when a future engineer would otherwise have to re-derive the reasoning.

---

## D-001 · The mutation gate's cap is a measurement value, not a permanent one

| | |
|---|---|
| **Date** | 2026-08-05 |
| **Files** | `.github/workflows/testing.yml:213` |

**Context.** The `mutation` job had never finished. It read 65.7%, then 99.0% — both from
runs cancelled before `d85861c`, both **EXPIRED** — and both numbers were beside the point:
it was cancelled by `timeout-minutes: 10` at 997 of 1593 mutants.

**Alternatives.**
1. Cut the 77 timeout-mutants. **Falsified by measurement**: a timeout costs 2.234s
   and a non-timeout 2.326s in the same band. Free timeouts still leave 10.6 min.
2. Cache between runs. **Impossible in mutmut 3.3.1** — `__main__.py:268` overwrites
   `exit_code_by_key` with all-`None` before anything reads it. A restored cache saves
   23.3s of 593s.
3. Parallelise. `--max-children` already defaults to `cpu_count`.
4. Speed the slow tests. The per-mutant timeout has a hard **15.00s floor** from a `+1`
   term, so total achievable movement across all 1593 mutants is **0.5 seconds**.
5. Raise the clock.

**Decision.** Raise the clock to **100 minutes**. The number came from the owner
against a measured bracket: 10.8 min provable floor, 24.1 mid, 32.7 upper.

**Reasoning.** The cost is asymmetric. A cancelled run yields **zero information** and
must be re-run; an over-generous cap costs only the difference in minutes, and only
when something actually hangs. Three CI runs had already been burned learning nothing.

**Trade-off.** *Gained:* the gate can finish, so the real runtime becomes knowable.
*Lost:* a PR can now wait up to an hour on this gate.

**Impact.** The run finished in **24m14s** at **99.3%**. Every projection above is now
replaceable by a fact, and the cap can be set from evidence rather than arithmetic.
That is the point — Law 6, never optimize before measuring.

---

## D-002 · Confidence has no document-level scalar

| | |
|---|---|
| **Date** | 2026-08-05 (owner's decision A5; recorded here) |
| **Files** | `docs/CONFIDENCE_SPECIFICATION.md` §4 |

**Context.** Six aggregation methods were on the table for combining per-field
confidence into one document number.

**Alternatives, and how four were eliminated *without any labelled data*.** Marichal &
Mesiar, *Meaningful aggregation functions mapping ordinal scales into an ordinal scale*,
Aequationes Math. 77(3) 2009, **Corollary 5.7** (first proved by Orlov, 1981): a
symmetric, continuous, idempotent function on an ordinal scale is comparison-meaningful
**iff it is an order statistic function.**

```
ELIMINATED  mean · product · Bayesian pooling · Dempster-Shafer
            Not order statistics. On an ordinal scale their ORDERING FLIPS under a
            transformation the data permits. Product fails even at interval level:
            φ(x) = x + 1 reverses which of two documents ranks higher.
SURVIVING   min · worst_k
```

**Corollary 6.2** goes further: across **independent** ordinal scales the only
comparison-meaningful function is a **projection**. OCR, table-structure and
document-type are three different instruments, so `min` across them asserts
**commensurability** — that an OCR 0.70 is the same quantity of doubt as a
table-structure 0.70. That claim is strictly stronger than ordinality and needs data.

**Decision.** **No document-level scalar at all.**

**Reasoning.** `min ≥ t` is *identically* `∀i : cᵢ ≥ t`. The scalar adds nothing the
per-field floors do not already carry, and it creates a false affordance — inviting
someone downstream to average it, compare it across documents, or threshold it, all of
which are meaningless on this scale.

**Trade-off.** *Gained:* no meaningless number can be built on. *Lost:* there is no
single number to show on a dashboard, and anyone expecting one will have to be told why.

**Impact.** `confidence_report` is a **recorder, not a gate**. Six of the sixteen
confidence parameters are dead on arrival because there is no document scalar to
threshold. Recorded as F-005: the frozen `FieldConfidence` has no slot for instrument
or region, so the raw signal lives in the measurement log instead.

---

## D-003 · The raw confidence signal lives in the measurement log, not the artifact

| | |
|---|---|
| **Date** | 2026-08-05 |
| **Files** | `src/accountant_dad/engines/input_engine/measurement.py`, `artifacts/evidence.py` |

**Context.** Decision A8 requires the raw signal preserved per field, per region, **per
instrument**, with its origin. `FieldConfidence` is `(field_name, confidence)` — no slot
for either.

**Alternatives.** (1) Amend the frozen artifact schema to add the fields. (2) Put the
raw signal in the append-only measurement log.

**Decision.** The measurement log.

**Reasoning.** **A8 says preserve the raw signal. It does not say preserve it inside the
artifact.** The log is append-only, line-delimited, and is what a calibration run reads.
Amending a frozen contract to solve a problem a new file already solves is the worse fix
— it spends a §M amendment and widens a schema every downstream engine depends on.

**Trade-off.** *Gained:* artifacts stay immutable and frozen; no amendment spent.
*Lost:* the raw signal is no longer co-located with the artifact it describes, so
anything wanting both must join them by document id.

**Impact.** `measurement.py` must carry `instrument` and `region` per signal or the
raw signal has **no home anywhere**. That makes it load-bearing, not optional.

---

## D-004 · PaddleOCR is resolved at first use, not at import

| | |
|---|---|
| **Date** | 2026-08-05 |
| **Files** | `src/accountant_dad/engines/input_engine/reader.py` |

**Context.** `reader.py` reaches PaddleOCR through `importlib` because PaddleOCR ships
no `py.typed`, so a plain `import paddleocr` is itself a `mypy --strict` error under a
zero-new-suppressions gate. The lookup was written at **module scope**.

**Decision.** Move the `importlib.import_module("paddleocr")` call inside the
already-`@cache`d `_recogniser()` builder.

**Reasoning.** At module scope, importing the Input Engine **at all** required a ~500 MB
ML package to be present — so every gate that merely imports the package died at
collection. The `importlib` route was chosen precisely to avoid a hard dependency, and
resolving at import time defeated it. Inside the cached builder it costs nothing (it
already ran exactly once) and restores the intended property: the dependency is needed
to **run OCR**, never to **import the module that offers it**.

**Trade-off.** *Gained:* the package imports without the ML stack; every non-OCR gate
survives. *Lost:* a missing PaddleOCR now surfaces at first OCR call rather than at
startup — later, and therefore in a worse place. Accepted because the alternative made
six gates unrunnable.

**Impact.** The literal string stays in the file, so the AST test pinning this module's
dynamic imports still sees it — moving the call does not hide a technology swap from
the stack check.

---

## D-005 · PyMuPDF's licence is recorded, not resolved

| | |
|---|---|
| **Date** | 2026-08-05 |
| **Files** | `requirements-engine1.txt`, `KNOWN_FAILURES.md` F-001 |

**Context.** `pymupdf==1.28.0` reports *"Dual Licensed - GNU AFFERO GPL 3.0 or Artifex
Commercial License"* — read from installed metadata, not recalled. AGPL §13 obliges
anyone letting users interact over a network to offer them the complete source. A hosted
accounting platform is exactly that shape.

**Alternatives.** (1) Swap to a permissively licensed PDF reader. (2) Buy the Artifex
commercial licence. (3) Pin it, record the exposure, and escalate.

**Decision.** (3).

**Reasoning.** `docs/TECHNOLOGY_STACK.md:28` **locks** PyMuPDF. A locked component is
not swapped on an engineer's judgement, and `CLAUDE.md` §E.8 forbids removing what the
owner specified. A licence is also not the kind of evidence the stack's replacement
clause contemplates — that clause wants a measured superiority on accuracy, latency,
determinism, maintainability or reliability. This is a legal constraint, not a
measurement, so it goes to the owner intact.

**Trade-off.** *Gained:* the lock holds and the exposure is visible in three places
(the requirements file, `KNOWN_FAILURES.md`, and the commit message).
*Lost:* the exposure is live in the meantime.

**Impact.** Blocks nothing technically. Blocks shipping to a paying customer until
route (1) or (2) is chosen.

---

## D-006 · Killed agents' work is recovered and finished, never restarted

| | |
|---|---|
| **Date** | 2026-08-05 |
| **Files** | process, not code |

**Context.** A session limit killed roughly 30 concurrent agents mid-run. Each had been
given an isolated git worktree.

**Alternatives.** (1) Re-dispatch every task from scratch. (2) Recover each worktree,
audit what survived, and finish from that checkpoint.

**Decision.** (2), always.

**Reasoning.** The worktrees persisted. 3,721 lines of source and 1,906 of tests
survived — restarting would have discarded all of it and re-derived the same three
defects. **State on disk is state**, and a summary is not a substitute for it.

**Trade-off.** *Gained:* nothing was lost, and inherited code got an audit pass it
would not otherwise have had — which is how the `DocumentId` import error and the
module-scope PaddleOCR import were caught. *Lost:* recovery is slower per task than
a clean restart would appear to be, and inherited code must be treated as untrusted.

**Impact.** Made permanent: `isolation: "worktree"` for every code-writing agent, and
recovery-before-restart as the standing response to any interruption.

**Superseded in part by D-015**, which adds the missing half: a recovered file is untrusted
until it has been *run* against the current contract, not merely committed.

---

## D-007 · A measurement belongs to the commit that produced it — Law 56

| | |
|---|---|
| **Date** | 2026-08-06 · **approved by the user** |
| **Files** | `CLAUDE.md` §C.56 · `ENGINEERING_RULES.md` "Commit-Bound Measurements" · `~/.claude/hooks/accountant-dad-commit-bound-metrics.py` · `LESSONS.md` L-011 · commits `6a5dbb3`, `c1eb9be` |

**Context.** A mutation score of **95.3% @ commit `7e0efe2`** — real, CI-produced, correct
— stayed quotable in reports while roughly 3,000 lines of source changed under it across
six modules. **Nothing was wrong with the number.** Everything was wrong with quoting it.

**Alternatives.**
1. Rely on care — re-check numbers before quoting them. Rejected: this *is* what was being
   done, and it failed silently. A judgement rule with no forcing function drifts (`§N`).
2. Timestamp measurements instead of binding them to commits. Rejected: a timestamp does
   not say which code produced the number, and two commits land in the same minute.
3. Bind every measurement to its commit, and make an uncited metric **unwritable**.

**Decision.** (3), enforced in **seven layers** so it cannot quietly lapse: the law ·
the rulebook section · a `PreToolUse` hook that rejects an uncited metric *before the write
lands* · the status-report format · the five progress documents · session memory · the
end-of-task self-audit.

**Reasoning.** The dangerous artifact is not a red metric — a red metric stops people. It is
a **green metric attached to source that has since moved**, read by someone deciding to
merge. Law 55 makes a below-threshold gate unmergeable; Law 56 is what stops an *expired*
green from impersonating a current one. Without it, Law 55 can be satisfied by arithmetic
performed on a fossil.

**The hook is deliberately narrow, and that is a design decision, not laziness.** It fires
only on a line carrying **both** a number with a unit **and** a measurement word, and never
on a line containing a threshold word — so `floor 93%` is silent and prose about coverage is
untouched. A hook that cries wolf gets switched off, and a switched-off layer enforces
nothing.

**Trade-off.** *Gained:* a stale number cannot be written into a progress document at all,
by anyone, including a future session that never read this entry. *Lost:* every metric now
costs the work of finding its commit, and a genuinely unknown value must be written as
**UNMEASURED** — which reads as less progress than a stale number would have implied. That
is the correct trade and it will feel like a regression.

**Impact.** Immediate and large. On the day it landed, **every** quotable number in this
repository expired: `src/` had moved `+2591 / −300` lines after `7e0efe2`. The five progress
documents now open with an explicit expiry block rather than a figure.

---

## D-008 · A third named state, never a widened boolean

| | |
|---|---|
| **Date** | 2026-08-06 |
| **Files** | `src/accountant_dad/engines/input_engine/confidence_report.py` · commit `502e166` |

**Context.** `RegionReading` refused `text` present with `extraction_confidence=None` — the
exact shape `reader.read_pdf_text_layer` emits for **every** region, because a text layer is
transcribed rather than recognised and no recogniser ran to produce a score. Three states
existed in reality; the invariant admitted two.

**Alternatives.**
1. Relax the invariant to allow `None` and let callers work out what it means.
2. Use a sentinel confidence value for "not measured".
3. Name the third state: `ReadingState.{UNREAD, READ_AND_SCORED, READ_BUT_UNSCORED}`.

**Decision.** (3).

**Reasoning.** (1) makes `is None` ambiguous at every call site, so each caller re-derives
the distinction and some get it wrong. (2) invents a number, which
`ENGINE_1_INPUT_ENGINE_RULES.md:625` forbids and Law 24 forbids generally. (3) follows the
`measurement.AbsentType` precedent that resolved F-005 — **absent, zero and unread are three
different claims and each gets a name.**

**Trade-off.** *Gained:* no caller re-derives the state from falsiness. *Lost:* a third
enum member every consumer must handle, and two existing tests had to be corrected —
stricter, not eased.

**Impact.** `state` tests `is None`, never falsiness, and that is **load-bearing**: the
minimum confidence is `Decimal("0")` and empty text is `""`, both falsy. Two tests pin those
collapses so a future refactor to `if not x` fails.

---

## D-009 · An unreadable document CROSSES the boundary as an artifact, never as an exception

| | |
|---|---|
| **Date** | 2026-08-06 |
| **Files** | `src/accountant_dad/engines/input_engine/pipeline.py` · commit `1e65b91` |

**Context.** Engine 1 raised where its contract says emit. A business outcome (*this scan is
unreadable*) was indistinguishable from a crash (*the code is broken*), so the Application
Layer could not route them differently. An unreadable receipt that should have become a
clarification question looked like an outage.

**The rule was already written, in three locked places** — read, not recalled:

```
APPLICATION_LAYER_CONTRACTS.md:30   business failure -> an object recording it
                                    runtime failure  -> nothing produced
APPLICATION_LAYER_CONTRACTS.md:27   never a fabricated one
COMMUNICATION_RULES_INPUT_ENGINE.md:159
                                    "The Input Engine does not halt the pipeline"
```

`parser.DocumentUnreadableError`'s own docstring had already assigned the job: *"The Input
Engine PARENT is what must not halt the pipeline."* `pipeline.run` is that parent and had
never implemented its half.

**Alternatives.** (1) Keep raising and let the Application Layer classify the exception
type. (2) Emit an artifact for every failure. (3) Emit for **business** failures only, and
keep raising for runtime ones.

**Decision.** (3), with the business/runtime line **read off the sub-engines' own declared
verdicts** rather than invented. `BUSINESS_FAILURE` holds four types:
`cleaner.UnusableArtifactError`, `reader.UnreadableDocumentError`,
`parser.DocumentUnreadableError`, `pymupdf.FileDataError` (measured: what a corrupt PDF
actually raises).

**Deliberately excluded, and this is the whole decision in one line.**
`VisionFallbackUnavailableError` and `ParserDependencyMissingError` keep raising. **A missing
TOOL is not a bad document.** Emitting *"unreadable"* for those would assert something false
about the user's file, which is worse than crashing.

**Trade-off.** *Gained:* the Application Layer can finally route a bad scan differently from
an outage. *Lost:* two error paths now exist where there was one, and the classification
must be maintained as new error types appear.

**Impact.** Nothing is fabricated in the failure artifact: `confidence_scores=()`,
`detected_fields=()`, `detected_tables=()`. One `UncertaintyMarker` carries the stage and the
sub-engine's own message verbatim. It is **deliberately not routed through
`assembly.assemble`** — that function requires all four sub-engine outputs precisely to prove
all four ran, and feeding it a manufactured `CleanerOutput` would be the fabricated object
line 27 forbids. The trade-off is stated in the module docstring rather than hidden.

---

## D-010 · The dependency closure is derived from module-scope imports, and only those

| | |
|---|---|
| **Date** | 2026-08-06 · the one `.github` line **approved by the owner** |
| **Files** | `pyproject.toml` · `tests/unit/test_declared_dependencies.py` · `.github/workflows/quality.yml:42` · commit `839645a` |

**Context.** `pyproject.toml` declared only `pydantic` while Engine 1 imports cv2, numpy,
PIL and pymupdf at module scope. Measured on a stdlib-only interpreter: `import
accountant_dad` succeeded; `...input_engine.cleaner` raised `No module named 'cv2'`. Four of
nine Engine 1 modules were unimportable from a correct install, and `quality.yml:47` imports
the **top-level package only**, which has no heavy imports — so the gate was green while the
installable artifact was broken.

**Alternatives.** (1) Copy `requirements-engine1.txt` wholesale. (2) Declare everything
Engine 1 can ever reach, including the ML stack. (3) Declare exactly what is imported **at
module scope**, and nothing resolved inside a function.

**Decision.** (3). Every version copied character for character from
`requirements-engine1.txt`; **none was chosen here.**

**Reasoning.** What CI happens to install is a different question from what the wheel
promises, and only the wheel's promise binds a user. (2) would put ~2 GB of ML wheels behind
`import accountant_dad` to no purpose — `docling`, `pypdfium2`, `torch`, `transformers` and
`paddleocr` are all reached through `require_module()` inside a function, so the package
imports without them and names the missing one when the work that needs it actually runs.

**Trade-off.** *Gained:* `pip install accountant-dad` produces an importable Engine 1.
*Lost:* the module-scope/function-scope distinction is now load-bearing, so moving an import
to the top of a file silently changes the package's contract.

**Impact.** That last risk is why the guard **derives** the set structurally from the AST
rather than restating it: a hand-maintained list drifts, a derived one cannot. The one
approved `.github` line resolves the install closure from the wheel's own metadata instead of
a hardcoded pin, so it never goes stale when a dependency changes.

---

## D-011 · A guard states its own limit rather than claiming to prove absence

| | |
|---|---|
| **Date** | 2026-08-06 |
| **Files** | `tests/unit/test_package.py` · `tests/unit/test_runtime_library_versions.py` · `tools/ci/assert_imports_match_pins.sh` |

**Context.** Two guards were checking the label instead of the thing.

```
the build freeze     matched module FILENAMES against FROZEN_MARKERS, opened no
                     file. engines/input_engine/gst_rates.py, full of tax logic,
                     PASSED
the version pin      asserted importlib.metadata.version("opencv-python") ->
                     '5.0.0.93' while cv2.__version__ reported '4.10.0'
```

Amendment 3 rests on the first, and its own wording gave the game away: *"a test proves no
module **named** for accounting, tax, LLM, brain or Tally enters it."* **Named** was doing
all the work.

**Alternatives.** (1) Extend the filename marker list. (2) Read the code. (3) Read the code
**and** write down what the check still cannot see.

**Decision.** (3). The freeze guard now parses each Engine 1 module with `ast` and inspects
imports, calls, function and class definitions, names, attributes, arguments and aliases —
including `importlib.import_module("x")`. The version guard asserts what the **imported
library reports about itself**, never what packaging metadata claims.

**Reasoning.** The general claim — *no accounting reasoning lives inside Engine 1* — is not
statically decidable, and **a guard claiming to prove it would be a worse lie than the
filename check.** So three narrow, checkable claims are proved instead (no cross-boundary
import, no AI vendor package, no accounting or tax identifier declared) and the residue is
written down. On the version side, metadata describes what was *installed*; only the module
knows what was *loaded*, and the gap between them is exactly where F-002 hid for a day.

**Trade-off.** *Gained:* both guards now measure the thing rather than its label. *Lost:*
the freeze guard is no longer a one-line claim anyone can hold in their head, and the
residual risk is now explicit and permanently visible.

**Impact.** Amendment 3's gate count rose as promised, and the honest limit is on the record
so nobody later mistakes these three tests for a proof of the general claim.

---

## D-012 · A crash is not an enforcement, and an omission must become a sentence

| | |
|---|---|
| **Date** | 2026-08-06 |
| **Files** | `src/accountant_dad/conformance.py` · `conformance_registry.py` · commit `e921c3c` |

**Context.** Two silent failures in the conformance harness.

1. A negative control that **crashed** — a validator reaching into a missing key, a builder
   calling a name that moved — scored as `ENFORCED`. The rule was never reached, so nothing
   was established either way, and the suite was green about it.
2. **45 hand-listed rules against 143 prohibition clauses in `docs/`**, with nothing anywhere
   comparing the two. A rule absent from the registry was indistinguishable from a rule
   nobody ever wrote.

**Alternatives.** For (2): leave the gap and trust review · auto-generate rules from the
clauses · require every uncovered clause to be **listed with a reason**.

**Decision.** `Attribution.CONTROL_CRASHED` as a fourth outcome, and an exclusion inventory
in which **every one of the 143 clauses is either cited as a rule or listed with one of four
reasons.**

**Reasoning.** *"The omission is silent and the suite is green"* is the most dangerous shape
a registry can have. Auto-generating rules would manufacture predicates for clauses that
have none, which is the fake-coverage failure in a new costume. A written reason is something
a human can argue with; an empty space is not.

**Backward compatibility was chosen over correctness, deliberately (Law 33).** Narrowing the
default by fiat would silently reclassify every control anyone ever wrote against this
harness, **including ones outside this repository.** The default stays the **old** behaviour,
stated out loud; the real inventory opts into the narrow one, and a test asserts that every
control in it did — so forgetting is red, not quiet.

**Trade-off.** *Gained:* a coverage gap is now a written sentence with an owner. *Lost:* 143
clauses must each be justified, and eight `REVIEW_ONLY` prohibitions must name the phase at
which the exemption expires.

**Impact.** The module also states what it still does **not** measure: *"whether any ENGINE
emits a conformant artifact… not one of them runs Engine 1."* **This decision shipped
incomplete** — the `Exclusion` dataclass it describes was never written, and the suite
cannot collect. Recorded as F-024.

---

## D-013 · A measurement is never computed from the rule that caused the damage

| | |
|---|---|
| **Date** | 2026-08-06 |
| **Files** | `src/accountant_dad/engines/input_engine/cleaner.py` · `tests/unit/test_input_engine_cleaner_redteam.py` · commits `1e0df65`, `590c6bb` |

**Context.** Four separate `cleaner` defects — a crop discarding a readable GSTIN, a net ink
count that went negative while ink was destroyed, a multi-page scan reporting page one only,
and an alpha channel discarded so two different documents cleaned to identical bytes. Each
destroyed document content **and reported that it had not.**

**Decision.** Treat them as **one class and fix the class** (§I.12): *a destructive step, or
the audit that reports on it, consulted the rule that caused the damage.* The crop's
retention was counted with the same Otsu mask that drew the box; the ink loss was a
difference of two counts under the same split; the page measurement used page one's rule for
every page; the greyscale conversion applied a luma that defines alpha out of existence.

**Reasoning.** Fixing four instances leaves the fifth. The invariant is that **the auditor
must not share a criterion with the actor** — the box is now drawn from the line profiles and
the retention counted at Otsu's split, two independent rules, so the figure can move.

**Trade-off.** *Gained:* the reporting figures can now report. *Lost:* two independent
criteria must stay independent, which is a property nothing enforces automatically.

**Impact.** Twenty-two red-team tests, all green. Each attack was kept **pointed at the
defect rather than retired with it**: where a fix made the original attack unconstructible,
the test was rewritten to hold both halves — the damage must not recur **and** the figure
that would report it must remain able to. One mutation **survived** all four break-attempts
and is recorded in the docstring rather than papered over; **no page is known that kills it
and none was invented to.**

---

## D-014 · Position decides a heading, not a score

| | |
|---|---|
| **Date** | 2026-08-06 |
| **Files** | `src/accountant_dad/engines/input_engine/classification.py` |

**Context.** A goods receipt note whose body prose read *"Received against your purchase
order…"* was classified from the catalogued phrase alone, as though the document had printed
PURCHASE ORDER as its own heading. A catalogued phrase appearing **anywhere** counted as
evidence of type.

**Alternatives.** (1) Score cues by position and threshold the score. (2) Hard-code which
document regions count as headings. (3) Ask whether the cue **opens or closes its own
region**.

**Decision.** (3). `_opens_or_closes_its_region` is the whole test: a heading either **is**
its region or **opens** it — `"TAX INVOICE"`, or `"TAX INVOICE - ORIGINAL FOR RECIPIENT"`.

**Reasoning.** (1) invents a number, and `classification` was built specifically to have
none — parameter #9 `classification_accept` stays UNSET and there is no cutoff to look up.
(2) would put knowledge of the layout vocabulary inside this module, where it does not
belong.

**Trade-off, stated rather than hidden.** *Gained:* body prose no longer names the document's
type. *Lost, in both directions:* a sentence that opens a prose region — *"This is not a TAX
INVOICE"* — still reads as evidence, because nothing structural separates it from a printed
heading; and a heading welded to layout noise stops being read as a heading, which is the
artefact-induced false negative already pinned elsewhere.

**Impact.** `UNKNOWN` now distinguishes two different situations — nothing catalogued was on
the page at all, versus something catalogued was on the page but not where a heading sits —
and says which. Still **zero numeric comparisons** in the module, guarded by the AST test
that walks its own source.

---

## D-015 · Recovered work is untrusted until it has RUN, not until it is committed

| | |
|---|---|
| **Date** | 2026-08-06 |
| **Files** | process, not code. Evidence: commits `211c6b0`, `6b32425`, `b3c1b51` |

**Context.** D-006 made recovery-before-restart permanent and it is still correct — no work
was lost again. But `211c6b0` recovered ten files from a session that **predated a signature
change**, and `b3c1b51` fixed the Application Layer's side of that same call while two test
files were never told. Measured at `e921c3c`: **39 of 40 failures are one line**,
`run() missing 1 required keyword-only argument: 'recorded_at'`.

**Alternatives.** (1) Do not commit unverified recovered work. (2) Commit it, and treat the
commit as the checkpoint. (3) Commit it immediately **and** record, in the commit itself,
that it is unverified and against which contract it was written.

**Decision.** (3). `211c6b0` and `6b32425` both did this correctly — *"Known-red on arrival,
by my own measurement, not a claim inherited from the previous agent"* — and it is now the
standing rule.

**Reasoning.** (1) loses work to the next interruption, which is exactly what D-006 exists to
prevent. (2) is what produced F-025: a green-looking commit whose tests cannot run. A
recovered file carries the contract it was written against, and **committing does not
re-derive that contract.**

**Trade-off.** *Gained:* nothing is lost, and nothing is silently trusted. *Lost:* the branch
now carries commits that are deliberately red, and from outside they are indistinguishable
from commits that are accidentally red — which is F-026.

**Impact.** Two rules follow. A recovery commit **must** state what it measured, not what the
previous agent claimed. And a branch carrying deliberate reds **must not be pushed as if it
were finished** — which is why 24 commits sit unpushed, and why that is itself now tracked.

---

## D-016 · CI job timeouts raised from 10 to 20 and 30 minutes

**Context.** `unit tests` and `coverage` both carried `timeout-minutes: 10`. The
suite grew from ~2,400 to **3,264 tests** as Engine 1 was completed, and the
`coverage` job runs the suite **twice** — once for the head, once for the base
branch to compute the ratchet.

**Measured, from real GitHub runs** (not local; runner speed is what decides this):

```
unit tests    max 6.87 min    successes 4.83 – 6.15 min
coverage      max 9.67 min    successes 5.73 – 6.80 min
```

Those ran at ~2,400 tests. At 3,264 the projection is `unit tests ≈ 9.3 min` and
`coverage ≈ 13.2 min`. **`coverage` cannot fit in 10 minutes and `unit tests`
would be a coin flip.**

**Alternatives considered.**

| Option | Rejected because |
|---|---|
| Make the suite faster | The top 25 tests are 38% of the time; the rest is spread across ~2,800 tests doing real Engine 1 work on real documents. Trimming the two outliers buys ~60s against a multi-minute gap. |
| Drop or skip slow tests | Making a gate pass by measuring less. Law 4, §J.4. |
| A very large ceiling (e.g. 360) | A timeout is a kill switch, not a target. At 360 a deadlock burns six hours of runner time before surfacing. Fails the stated criterion *"does not waste CI time."* |

**Decision.** `unit tests` **10 → 20**, `coverage` **10 → 30**.

**Reasoning.** Roughly **2.2×** the projected runtime for each. GitHub runner
speed varies about 2× on a bad day, so 2.2× absorbs that without hiding a hang:
a genuine deadlock now surfaces in 20–30 minutes rather than 6 hours.

**Trade-off.** Gained: two required gates that can actually complete. Lost: a
hung job now costs up to 30 runner-minutes instead of 10. Accepted, because a
gate that cannot finish provides no signal at all.

**Impact.** `.github/workflows/testing.yml`, two lines. No gate added, removed
or renamed; the count stays 23. No other value touched.

**Revisit.** These are measurements, not preferences. If later runs show the
suite is faster, lower them; if it grows, raise them. The rule is the smallest
value that completes stably.

**Authority.** Delegated by the owner, 2026-08-06, with the explicit instruction
to measure real runs and justify the value here.
