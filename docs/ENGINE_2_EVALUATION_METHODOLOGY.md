# Engine 2 — Evaluation Methodology

> **Precedence level 3 — Engine Specifications.** Subordinate to
> [`SYSTEM_INVARIANTS.md`](SYSTEM_INVARIANTS.md),
> [`MEASUREMENT_FRAMEWORK.md`](MEASUREMENT_FRAMEWORK.md),
> [`EVALUATION_PROTOCOL.md`](EVALUATION_PROTOCOL.md),
> [`GOLDEN_DATASET.md`](GOLDEN_DATASET.md),
> [`ACCOUNTING_DEFINITIONS.md`](ACCOUNTING_DEFINITIONS.md) and
> [`ADVERSARIAL_TESTING.md`](ADVERSARIAL_TESTING.md).
> **Where this document and any of those differ, they win and this one is wrong.**
>
> **⬜ DESIGN ONLY. NOTHING HERE IS IN FORCE.** No implementation exists and none is
> authorized — `CLAUDE.md` §P **Amendment 4 is an unsigned DRAFT** and
> `ENGINE_2_AUTHORIZED` in `tests/unit/test_package.py:170` is `frozenset()`.
>
> **This document performs no amendment.** It *drafts* several, names them as
> drafts, and names the owner who must sign each. A locked document is not
> changed by a sentence written in a subordinate one.
>
> **This document subtracts nothing.** Every threshold, metric, condition and
> protocol step in a locked document stands unchanged. Everything below is an
> **addition** or an **owner question**, per `CLAUDE.md` §E.8.

---

## 0. The one question

> **How would we ever know Engine 2 works?**

Engine 2's output is *understanding* — a word `CLAUDE.md` **Law 54** lists as one of
seven load-bearing undefined terms, against the entry *"Engine 2's entire output."*

It is no longer undefined. [`ACCOUNTING_DEFINITIONS.md`](ACCOUNTING_DEFINITIONS.md) §2
defines it and gives it a measurement. **This document's first job is to audit that
definition rather than assume it**, and the audit's verdict is the most valuable thing
here:

> **The test is fully operational. The threshold is not, because the denominator it is
> a fraction of measures a different thing from the numerator.**
>
> **And the test is blind to four of the five failures Engine 2's own specification
> names — including, in an identifiable class of cases, scoring the honest story below
> the dishonest one.**

Both are stated precisely in §1 and §2, with the lines that prove them, **and §1.4.1
records the attempt to disprove the second and the ground it lost.**

**A second finding, larger than either and found while designing the calibration plan, is
in §8 (WL-4):**

> **`evidence_reliability` — the fourth term the §M amendment puts inside its `min()` —
> is not a quantity that exists.** The Document Evidence Object carries per-field
> confidences and a prose string; it carries **no reliability scalar at all**, and no
> document specifies the function that would produce one. It was measured off the built
> classes, not inferred.

---

## 1. The measurable finish line (Law 52, `CLAUDE.md` §G2)

### 1.1 What the locked documents already supply

Three locked documents state the same number, and it is not invented here.

[`ACCOUNTING_DEFINITIONS.md`](ACCOUNTING_DEFINITIONS.md) §2:

```
REQUIRED:  understanding correctness ≥ 80% of the frozen ceiling
```

[`MVP_IMPLEMENTATION_BLUEPRINT.md`](MVP_IMPLEMENTATION_BLUEPRINT.md) §1, finish
condition **7**: *"**Understanding** — accountant reaches the same treatment from the
story alone | **≥ 80% of the frozen ceiling**"*.

The same document, §3, P6 done-when: *"**understanding ≥ 80% of ceiling**"*.

And the measurement, [`ACCOUNTING_DEFINITIONS.md`](ACCOUNTING_DEFINITIONS.md) §2:

> **a qualified accountant reading only the Transaction Story — never the source
> document — independently produces the same accounting treatment they produced from
> the document itself.**

Four steps, in order: treatment **from the document**, recorded · a **separate sitting,
minimum one week later** · treatment **from the Transaction Story alone** · compare.
*"Produces, not approves."*

### 1.2 The finish line, stated as one number with a unit

```
understanding correctness
  =  N of M golden documents on which a qualified accountant, reading ONLY the
     Transaction Story and never the source document, independently reproduces the
     accounting treatment they produced from the document itself — all four fields
     exact per ACCOUNTING_DEFINITIONS.md §1, worst of 3 runs, in GitHub CI.

unit :  documents, reported as "N of M", never as a bare percentage
```

Its threshold, as the documents write it:

```
understanding correctness  ≥  80% of the frozen ceiling
```

### 1.3 The four things that make that threshold uncomputable today

**80% is supplied. What it is 80% *of* is not.** Each of the four below is an owner
decision. None is inventable by an engineer (Law 52, Law 54), and each changes the
number.

---

#### OD-1 · WHICH ceiling is "the frozen ceiling" for understanding?

**This is the blocking one.** The others change the number; this one decides whether the
number means anything.

`ceiling.json` holds **inter-rater agreement**.
[`MEASUREMENT_FRAMEWORK.md`](MEASUREMENT_FRAMEWORK.md) §1:

> `inter-rater agreement = documents where both produced an identical entry`

Two people · one document · one sitting.

The understanding test is **one person · two different inputs · two sittings a week
apart**. It is not the same measurement, and *"80% of it"* is therefore a fraction of a
quantity that never measured the task being scored.

The nearest human control the framework already has is **intra-rater** agreement — same
document, same person, later. [`MEASUREMENT_FRAMEWORK.md`](MEASUREMENT_FRAMEWORK.md) §1.4:

> **Intra-rater agreement is also measured**: 2 documents re-labeled by the **same**
> person ≥ 2 weeks later. **A person disagreeing with themselves is the true noise
> floor**, and system errors below it are unattributable.

Two problems even with that:

| Problem | Evidence |
|---|---|
| **The intervals disagree** | understanding uses *"minimum one week"* (§2 step 2); intra-rater uses *"≥ 2 weeks"*. Two protocols, so not the same control |
| **N = 2** | An 80%-of-ceiling gate on a denominator of **2 documents** moves 50% on one document. [`MEASUREMENT_FRAMEWORK.md`](MEASUREMENT_FRAMEWORK.md) §5 already rejects a milder version of this shape: *"a 3-document gate moves 33% on a single failure. **The final gate cannot be the noisiest number in the system.**"* |

**THE DECISION — pick one.**

**(a) Use `ceiling.json` — inter-rater — exactly as the sentence literally reads.**
*Failure mode:* the denominator measures a different task. The system is credited or
penalised for a human disagreement it never saw. Costs nothing extra.

**(b) Use intra-rater, widened from 2 documents to all 16, and its interval aligned to
one week.** *Failure mode:* 16 more accountant sittings —
[`MEASUREMENT_FRAMEWORK.md`](MEASUREMENT_FRAMEWORK.md) calls accountant time *"the
scarcest resource."* Also still the wrong task: it re-reads the *document*, not a story.

**(c) A purpose-built understanding ceiling: each labeller reproduces the treatment from
their OWN stage-2 story, ≥ 7 days later, document withheld.**
*Failure mode:* one extra sitting per labeller per document, and an accountant's own
story is not the story Engine 2 writes, so the ceiling measures the *task* and not the
*writer*.

**Recommended: (c).** It is the only option where numerator and denominator are the same
measurement — a human performing the identical task the machine is scored on. Under
(a) or (b), *"80% of the ceiling"* is a ratio between two different quantities, which is
not a threshold, it is a coincidence with a percent sign.

**The owner decides. This document does not.**

---

#### OD-2 · There is no absolute floor for understanding

[`MEASUREMENT_FRAMEWORK.md`](MEASUREMENT_FRAMEWORK.md) §1, anti-gaming rule 2:

> **The target is dual.** Both must hold:
> ```
> system ≥ 80% of frozen ceiling      (relative)
> system ≥ absolute floor             (absolute — set at sign-off)
> ```
> Without the floor, worse labelers make the target easier — a lower ceiling would
> *reduce* what the system must achieve. **The floor makes that impossible.**

[`MVP_IMPLEMENTATION_BLUEPRINT.md`](MVP_IMPLEMENTATION_BLUEPRINT.md) §1 applies this
rule to correctness — conditions **1** *and* **2**, and says why: *"Conditions 1 and 2
are dual on purpose. A relative target alone is gameable."*

**Condition 7 has only the relative half.** Understanding is therefore gameable in
exactly the manner the framework's own rule names, and the rule is simply not applied
to it.

**THE DECISION:** set an absolute understanding floor, as `N of 16 documents`.
**The number is UNSET and is not chosen here** (Law 52 — *"Never infer it. Never pick
one yourself and proceed."*).

*Failure mode of leaving it unset:* a low understanding ceiling silently lowers the
understanding bar, and nothing in the suite would report that it had moved.

---

#### OD-3 · One labeller, or two?

[`GOLDEN_DATASET.md`](GOLDEN_DATASET.md): *"**Both accountants label all 16 golden
documents**, blind to each other and blind to the system."*
[`ACCOUNTING_DEFINITIONS.md`](ACCOUNTING_DEFINITIONS.md) §2 is written throughout for a
singular *"the accountant."*

**THE DECISION — pick one.**
**(a) AND** — correct iff both labellers reproduce their own treatment. Strictest; the
number will be lowest. **(b) OR** — correct iff at least one does. **(c) Two numbers,
per labeller, never averaged** — consistent with
[`PHASE_REPORT_TEMPLATE.md`](PHASE_REPORT_TEMPLATE.md): *"Never average across engines.
Six numbers stay six."*

**Recommended: (c) for reporting, (a) for the gate.** Report both, gate on the stricter.

---

#### OD-4 · Do disputed documents leave the understanding denominator?

[`ACCOUNTING_DEFINITIONS.md`](ACCOUNTING_DEFINITIONS.md) §1, on entry correctness, when
two accountants disagree: the document *"leaves the correctness denominator"* and
*"joins the **ask-or-not set**."* Nothing states whether the same happens to the
**understanding** denominator.

It arguably should not. Understanding is measured **per labeller against themselves**, so
labeller A can be perfectly self-consistent on a document A and B answer differently.
Dropping it would discard a valid measurement — and at M = 16, every document counts.

**THE DECISION — pick one.** **(a) Keep them** — raises N, one extra rule to remember.
**(b) Drop them** — one denominator rule across the whole suite, N falls.
**Recommended: (a)**, with the disputed documents listed separately in the report.

---

#### OD-5 · Which set — held-out, development, or both?

Condition **1** names the set explicitly (*"worst of 3, held-out"*). Condition **7** does
not.
[`MEASUREMENT_FRAMEWORK.md`](MEASUREMENT_FRAMEWORK.md) §5 seals held-out and permits one
open per phase.

**Recommended: held-out, matching condition 1**, with the development figure reported
alongside and clearly marked as tuned-against. A metric measured only on the set you
developed against is a memorisation score.

---

### 1.4 The finish line is NECESSARY and is not SUFFICIENT

**This is the finding this document exists to deliver — and it is stated at the strength
it survived being attacked at, not at the strength it was first written at. §1.4.1
records the attack and what it took away.**

[`ENGINE_2_UNDERSTANDING_ENGINE_RULES.md`](ENGINE_2_UNDERSTANDING_ENGINE_RULES.md) §14
names five ways the engine fails:

> - ❌ A fact is invented to complete the story.
> - ❌ A conflict is silently resolved.
> - ❌ An unknown is dropped because the narrative reads better without it.
> - ❌ Confidence is raised above what the evidence supports.
> - ❌ Accounting vocabulary appears in the output.

Now hold each against §2's metric — *accountant reads the story alone, produces a
treatment, compare*:

| Named failure | Does the §2 metric detect it? |
|---|---|
| **1 · Invented fact** | **No, in general.** Only if the invention changes the treatment. An invention that is correct by luck scores **CORRECT** |
| **2 · Conflict silently resolved** | **No.** A conflict resolved the way the accountant would have resolved it scores identically to an honest one. See §1.4.1 |
| **3 · Unknown dropped** | **No.** A gap the accountant would have filled the same way scores identically to a gap honestly named |
| **4 · Confidence raised above evidence** | **No.** The story-only sitting never shows a confidence value. **Undetectable by construction** |
| **5 · Accounting vocabulary** | Detectable — but by a predicate, not by this metric. Already built: `AuthoredText` in `src/accountant_dad/artifacts/understanding.py` |

**Four of the five are invisible to the finish line.** That alone makes it necessary and
not sufficient, and it is the whole argument for U-1 … U-5 below.

[`ENGINE_2_UNDERSTANDING_ENGINE_RULES.md`](ENGINE_2_UNDERSTANDING_ENGINE_RULES.md) §10
says why blindness here is not a small thing:

> The incorrect output is wrong **even when ₹50,000 turns out to be right.** It is wrong
> because nothing downstream can tell that a choice was made.

**A metric that cannot tell a choice was made cannot enforce that sentence.**

#### 1.4.1 The stronger claim, attacked — and what the attack took away

**First written, this section claimed the metric actively *rewards* silent conflict
resolution. That claim is too strong and is withdrawn. The attempt to disprove it is
recorded here rather than deleted** (`CLAUDE.md` §D.13 — *"try to PROVE yourself WRONG"*).

**The attack.** Take the §10 worked example: the invoice says ₹50,000, the payment record
says ₹45,000.

- Reading the **document**, the accountant sees both figures and produces one entry —
  say ₹50,000, by judgement.
- Reading a **conflict-preserving story** — *"two amounts exist; mismatch; unresolved"* —
  they see both figures again, apply the same judgement, and produce **₹50,000**.
- **Same treatment. Scores CORRECT.**

**An honest story is not information-poorer than a resolved one. It is
information-richer.** So preservation is not generally penalised, and the original claim
fails.

**What survives the attack — a narrower class, and it is real.**

The penalty appears when **the story surfaces something the accountant did not act on
when reading the document.** Line items summing to ₹49,999 against a stated total of
₹50,000 is a discrepancy easy to miss on a page and impossible to miss in a sentence
that names it.

```
document sitting   discrepancy not noticed  ->  entry at 50,000
honest story       discrepancy named        ->  accountant now asks, or answers
                                                differently  ->  DIFFERENT  ->  INCORRECT
resolved story     discrepancy hidden       ->  entry at 50,000  ->  SAME  ->  CORRECT
```

**In that class, the honest artifact scores below the dishonest one.** It is narrower
than first claimed and it is not hypothetical — golden document 8 is built to be exactly
this shape ([`GOLDEN_DATASET.md`](GOLDEN_DATASET.md): *"**Internal contradiction** — line
items don't sum to the total | A finding, not a guess"*).

**And it collides with an existing rule rather than resolving cleanly.** When the system
surfaces something the labeller missed, [`GOLDEN_DATASET.md`](GOLDEN_DATASET.md)'s
immutability rule governs: *"If the system disagrees and appears right: **Record the
disagreement. Do not edit.**"* — the accountant re-labels independently, blind, and both
versions are kept. **So the class is handled, but by a procedure outside this metric, and
the metric itself still scores the honest story as a miss until that procedure runs.**

**What this changes, and what it does not.** The conclusion — necessary, not sufficient,
add U-1 … U-5 — is unchanged, because it rested on the blindness in the table above and
not on the withdrawn claim. **What changes is the strength of the sentence, and a
document that quietly kept the stronger version would have been wrong in the reassuring
direction.**

§14's asymmetry still stands over all of it, and it is what U-1 … U-4 exist to enforce
where the finish line cannot:

> a story that is incomplete and honestly marked is a **success**. A complete, coherent
> story built on one quiet assumption is a **failure**, even when the assumption is
> correct.

#### The fix is additive, never subtractive

Condition 7 stays exactly as written. **Four companion measures are added**, each a
**count and not a rate**, and each carrying the failure §2 cannot see. The count-not-rate
shape is copied from [`ACCOUNTING_DEFINITIONS.md`](ACCOUNTING_DEFINITIONS.md) §4, which
already reasons this way: *"the statutory-under-rating condition is a count, not a rate,
and one occurrence fails it regardless of N."*

| # | Measure | Definition | Required | Carries |
|---|---|---|---|---|
| **U-1** | **Fabricated evidence references** | facts in the Business Understanding Object whose `evidence_references` do not resolve to a region of a Document Evidence Object under the same Transaction ID | **0** | failure 1 |
| **U-2** | **Conflicts dropped** | conflicts the labellers recorded as present in the evidence that the artifact does not carry | **0** | failure 2 |
| **U-3** | **Required unknowns dropped** | gaps a labeller marked as *must be named for the treatment to be decidable* that the artifact does not carry | **0** | failure 3 |
| **U-4** | **Confidence breaches** | artifacts where understanding confidence exceeds evidence reliability, or exceeds the lowest sub-engine confidence | **0** | failure 4 |

And one reported alongside, as a rate rather than a count, because over-reporting is
tolerable and under-reporting is not — the same asymmetry
[`EVALUATION_PROTOCOL.md`](EVALUATION_PROTOCOL.md) applies to over-asking versus
SILENT-WRONG:

| # | Measure | Definition | Reported |
|---|---|---|---|
| **U-5** | **False unknowns** | unknowns which, when the missing fact is supplied and the case is re-run, change no field of the treatment | rate, with N |

**U-5 reuses the §5 Doubt falsifier unchanged** —
[`ACCOUNTING_DEFINITIONS.md`](ACCOUNTING_DEFINITIONS.md) §5: *"Supply the fact. Re-run…
The decision does not change → **Not a doubt.**"* One mechanism, two consumers
(`CLAUDE.md` Law 15 — reuse before building; Law 14 — never duplicate logic).

**U-4 is already enforced structurally**, and it was verified rather than assumed —
`ConfidenceAssessment._understanding_never_exceeds_evidence` and
`BusinessUnderstandingObject._nothing_the_results_raised_was_lost` in
`src/accountant_dad/artifacts/understanding.py` refuse both breaches at construction.
**U-1 is not enforced at all** — see §7, attack E2-1, where it is demonstrated.

### 1.5 The finish line, whole

```
REQUIRED — all six, simultaneously, on one pre-registered non-void CI run

  understanding correctness  ≥ 80% of the frozen UNDERSTANDING ceiling   [OD-1: UNDEFINED]
                             AND ≥ the absolute understanding floor      [OD-2: UNSET]
  U-1 fabricated references  = 0
  U-2 conflicts dropped      = 0
  U-3 required unknowns dropped = 0
  U-4 confidence breaches    = 0
  U-5 false unknowns         reported with N — no threshold proposed here
```

> **Only the first line exists in the locked documents, and it is the one that cannot
> be computed.** 80% is supplied; the denominator is not defined for this measurement.
> **OD-1 and OD-2 are the finish line. Everything else in this document can be designed,
> built and run without them.**

---

## 2. Is "Understanding" measurable as written? — the audit

**Verdict: the TEST is. The THRESHOLD is not.**

### What is measurable exactly as written — no gap

Every step of §2's protocol is executable with no undefined term:

| Step | Executable? | Why |
|---|---|---|
| Treatment produced from the document | ✅ | It is `stage_3_entry`, already in [`GOLDEN_DATASET.md`](GOLDEN_DATASET.md)'s protocol |
| A separate sitting, ≥ 1 week later | ✅ | A timestamp difference. Checkable mechanically from the label file |
| Treatment produced from the story alone | ✅ | Same four fields, different input |
| Compare | ✅ | [`ACCOUNTING_DEFINITIONS.md`](ACCOUNTING_DEFINITIONS.md) §1's exact-four rule, unchanged. No new scoring rule needed |

**§2 is the most operational of the six definitions**, and its own claim for itself is
fair: *"This is the sharpest of the six because it tests the only property that matters:
**does the story carry enough to decide.**"*

**It also earns a defence.** §2 explains why the metric is not redundant with the
isolated/contributed gap, and the explanation is correct: the gap says Engine 2 lost
accuracy; this says **what** it lost, and *"Wrong needs Engine 2's reasoning corrected;
incomplete needs its output contract widened."* Those have different fixes. No other
metric in the suite separates them.

### What is NOT measurable as written — six gaps, precisely

| # | Gap | Consequence |
|---|---|---|
| **G-1** | The denominator (**OD-1**) names an artifact measuring a different task | The threshold is a ratio of two unlike quantities |
| **G-2** | No absolute floor (**OD-2**), though `MEASUREMENT_FRAMEWORK.md` §1.2 requires the target be dual | The bar moves with the ceiling |
| **G-3** | *"the accountant"* is singular; the dataset has two (**OD-3**) | Two defensible scoring rules, two different numbers |
| **G-4** | The evaluation set is unnamed (**OD-5**) | A development-set number is a memorisation score |
| **G-5** | Disputed documents' status is unstated (**OD-4**) | The denominator is ambiguous at M = 16, where one document is 6.25% |
| **G-6** | The metric is **necessary and not sufficient** — blind to four of Engine 2's five named failures, and scoring the honest artifact below the dishonest one in the narrow class §1.4.1 identifies | Four failure modes have no gate; golden document 8's shape is scored backwards until `GOLDEN_DATASET.md`'s re-labelling procedure runs |

### Two further undefined terms, found while auditing

Both are load-bearing, both sit inside the §M amendment, and neither is defined
anywhere. Law 54 — *"An undefined term in a specification is a false statement waiting to
be discovered."*

**OD-9 · `transaction class`.** The §M amendment requires calibration *"by transaction
class."* No locked document defines a transaction class. The nearest candidate is
`ENGINE_2:380`'s nine event kinds — and `SPEC_GAPS` in
`src/accountant_dad/artifacts/understanding.py` already records that vocabulary as
**open**:

> `"TransactionUnderstandingResult.identified_event — ENGINE_2:380, open"`

An **open** vocabulary cannot partition a corpus, because two labellers may name the same
class differently and no rule says they agreed. **Calibration by transaction class is not
computable until the term is defined and its vocabulary closed** — which is an amendment
to `ENGINE_2:380`, not an engineering choice.

**OD-6 · What event is Engine 2's confidence the confidence *of*?** The §M amendment
says *"calibrate confidence against labelled accounting datasets"* without naming the
outcome. Two candidates, both defensible, giving different curves:

- **(a)** understanding correct, per §2 — Engine 2's confidence predicts Engine 2's own
  output
- **(b)** the final entry correct, per §1 — which is what §M's five auto-post conditions
  actually gate on
- **(c)** both, two curves, never averaged

**Recommended: (c).** (a) is what the number claims to be about; (b) is what the policy
consumes. **A calibration curve with no named event is not a measurement.**

---

## 3. Evaluation protocol

> Shaped to mirror [`EVALUATION_PROTOCOL.md`](EVALUATION_PROTOCOL.md) rather than to
> replace it. **Its eleven steps, its eight preconditions and its void conditions apply
> unchanged.** Everything below is an addition.

### 3.0 Where it runs

**GitHub Actions. Nowhere else counts** (Law 44,
[`MEASUREMENT_FRAMEWORK.md`](MEASUREMENT_FRAMEWORK.md) §0a).

**With one honest exception that must be stated rather than fudged.** The understanding
sitting **requires a human, a week apart**. It cannot happen inside a CI job and
pretending otherwise would be theatre.

```
the SITTING            happens offline, produces a committed label file
the VERIFICATION       happens in CI, and is mandatory:
                         the file exists
                         its hash matches the pre-registration
                         the interval computed from its OWN timestamps is >= 7 days
                         the session record contains no reference to the source document
```

**The human step cannot be in CI. The verification of it can be, and therefore must be.**
A number whose provenance is only a person's recollection is not a result.

### 3.0a Executable preconditions — the harness REFUSES to run

[`EVALUATION_PROTOCOL.md`](EVALUATION_PROTOCOL.md) §0a's eight, **plus** these twelve.
Same principle, stated there: *"Not a gate you pass. A gate that will not start."*

| # | Precondition | Executable check |
|---|---|---|
| **E2-P1** | Running in CI | `GITHUB_ACTIONS=true` — local invocation refuses |
| **E2-P2** | Pre-registration committed first | git commit timestamp precedes run start |
| **E2-P3** | Artifacts commit-bound | every Business Understanding Object under evaluation hashed, hash bound to the evaluated commit (Law 56) |
| **E2-P4** | Understanding label file present | hash matches pre-registration |
| **E2-P5** | Sitting interval | `story_sitting_at − document_sitting_at ≥ 7 days`, computed from the file, **never asserted by a human** |
| **E2-P6** | Story-only sitting was blind | session record contains no `source_file`, no `stage_1_fields`, no page image |
| **E2-P7** | Story-only sitting saw ONLY the story | session record contains no sub-engine Result, no Identified Unknowns, no Confidence Assessment. §2 says *"reading only the Transaction Story"* |
| **E2-P8** | Conformance green | on every artifact under test — you cannot attribute a bad story to reasoning while the pipeline breaks its own rules |
| **E2-P9** | Vocabulary predicate green | every authored string in every artifact |
| **E2-P10** | Evidence references resolve | every reference resolves to a region of a Document Evidence Object under the same Transaction ID. **This check does not exist today — see E2-1** |
| **E2-P11** | Understanding ceiling frozen | hash matches its committed value |
| **E2-P12** | Model pinned | model · version · temperature · prompt hash match the frozen block. Per [`EVALUATION_PROTOCOL.md`](EVALUATION_PROTOCOL.md): *"A model change invalidates every previous number."* |

### The run — where Engine 2's steps slot in

[`EVALUATION_PROTOCOL.md`](EVALUATION_PROTOCOL.md)'s **Steps 0 – 5** run unchanged:
pre-register · freeze and record · drift canary · **negative controls FIRST** ·
conformance · baselines.

> **Step 5 has a hole for Engine 2 — OD-11.** The strong baseline is defined in
> [`MEASUREMENT_FRAMEWORK.md`](MEASUREMENT_FRAMEWORK.md) §4 as *"Regex field extraction +
> vendor→ledger lookup table + GST rate table"*, which produces an **entry**. Engine 2
> produces a **story**. **No strong baseline for a Transaction Story is defined
> anywhere**, so finish condition **4** — *margin ≥ 0.30 over the strong baseline* —
> cannot be applied to Engine 2 at all.
>
> **Candidate, for the owner:** a **template story** filled from Engine 1's extracted
> fields with no reasoning of any kind — *"On {date}, {party} supplied {items} for
> {amount}; payment status {status}."* That is §4's *"two weeks of ordinary scripting"*
> bar, transposed to this engine's output. If a language model cannot beat a template on
> the understanding metric, §4's verdict applies verbatim: *"The AI is doing nothing a
> lookup table doesn't. Stop and rethink — do not tune."*
>
> **It is a bar, so it is the owner's to set.** Not chosen here.

**Step 6 — Isolated pass, ×3.** Engine 2 fed the **golden** Document Evidence Object.
**BLOCKED — see §4.4.** The blocker is the artifact schema, not the accountants.

**Step 7 — Contributed pass, ×3.** Full pipeline. Record the worst. Record the spread.

**Step 7a — NEW · The understanding sitting.** Out of band, verified in CI per §3.0.
Produces `stage_2h_story_only_treatment` per labeller per document.

**Step 8 — Safety pass, ×10.** For Engine 2, *"wrong entry"* is downstream. **Engine 2's
safety analogue is U-1 … U-4, and each must be 0 in every one of the ten runs.** Ten
rather than three for the reason §2 of [`MEASUREMENT_FRAMEWORK.md`](MEASUREMENT_FRAMEWORK.md)
gives: *"a 1-in-10 catastrophic output has only a **27% chance of appearing in 3 runs**…
they cannot establish a zero. The zero is the entire point."*

**Step 9 — Compute.**

```
understanding correctness  = documents where the story-only treatment matches the
                             document-derived treatment on all four fields, worst run
ceiling fraction           = understanding correctness ÷ frozen understanding ceiling
absolute floor             = understanding correctness ≥ floor              [OD-2 UNSET]
inherited damage           = isolated − contributed                        [Step 6 blocked]
spread                     = best − worst        > 2 documents = failure regardless
U-1 … U-4                  counts, over all 10 safety runs
U-5                        rate, with N
```

**Step 10 — Headline numbers, separately.** Never summed, never netted:

```
understanding correct       N of M, worst run
UNDERSTANDING-INCOMPLETE    accountant could reach NO treatment from the story
UNDERSTANDING-WRONG         accountant reached a DIFFERENT treatment
U-1 fabricated references   count      <- must be 0
U-2 conflicts dropped       count      <- must be 0
U-3 required unknowns dropped  count   <- must be 0
U-4 confidence breaches     count      <- must be 0
U-5 false unknowns          rate, with N
```

> **INCOMPLETE and WRONG are reported apart, always.**
> [`ACCOUNTING_DEFINITIONS.md`](ACCOUNTING_DEFINITIONS.md) §2 makes them different
> findings with different fixes: *"Wrong needs Engine 2's reasoning corrected; incomplete
> needs its output contract widened."*
> [`MVP_IMPLEMENTATION_BLUEPRINT.md`](MVP_IMPLEMENTATION_BLUEPRINT.md) §5 goes further —
> incomplete *"is an amendment, not a tuning problem."* **Summing them destroys the only
> signal that says which.**

**Step 11 — Adversarial, then report.** §7 below, then
[`PHASE_REPORT_TEMPLATE.md`](PHASE_REPORT_TEMPLATE.md), **before** the commit.

### Void conditions — discarded, never adjusted

[`EVALUATION_PROTOCOL.md`](EVALUATION_PROTOCOL.md)'s conditions apply unchanged. These
are additional and Engine-2-specific:

| Condition | Why |
|---|---|
| **Sittings less than 7 days apart** | §2: *"an accountant who read the document an hour ago is not reading the story alone — they are reading it with the document in memory"* |
| **The document, page image, or the labeller's own stage-1 fields were available at the story sitting** | It is no longer a story-only test |
| **The six Results, Identified Unknowns or Confidence Assessment were shown alongside the story** | §2 says *"only the Transaction Story."* Showing more is a different, easier test |
| **The story was regenerated at a commit other than the pre-registered one** | Law 56 — the measurement belongs to a commit |
| **The understanding ceiling was re-measured without an amendment** | The bar was moved |
| **An unknown or conflict label was edited after the artifact was seen** | It now measures agreement, not correctness — [`GOLDEN_DATASET.md`](GOLDEN_DATASET.md)'s immutability rule |
| **The scoring rule for INCOMPLETE vs WRONG was written after a story was read** | It could have moved to fit |

### Honest reporting

- **Always `N of M`.** *"81%"* on 16 documents is *"13 of 16"*.
- **Always name which OD-1 option produced the ceiling**, on every line that quotes a
  ceiling fraction. A ceiling is a statement about what was compared.
- **U-1 … U-4 are counts and are never converted to rates.** A rate invites a threshold;
  these have none.
- **The scorer is the labeller and cannot be blinded.** §2's protocol requires the same
  person for both sittings. Recorded as a limitation on every report, per
  [`MEASUREMENT_FRAMEWORK.md`](MEASUREMENT_FRAMEWORK.md) §7.3 — *"the report records this
  as a limitation. Never waved away."*
- **Never average across labellers.** Two numbers stay two.
- **`NOT COMPUTABLE` and `FLAT` are different findings; swapping them is a Law 24
  violation, not a new prohibition this document invents.** A flat curve is a finding
  under §10 — *"Confidence is noise."* A curve with N = 1 per bucket is not a finding at
  all, and reporting the second as the first fabricates a result.

  > Phrased as a consequence rather than as an absolute, deliberately. The conformance
  > registry scans `docs/` for prohibition clauses and requires each to be cited by a
  > rule or listed as excluded. **A methodology document has no authority to mint a
  > prohibition** — the locked specifications and `CLAUDE.md` own those, and this one
  > only applies them. Stating it as an absolute here made
  > `test_every_prohibition_clause_in_the_documents_is_covered_or_listed` red, which is
  > the guard working exactly as designed.

---

## 4. Ground truth — what a labelled Engine 2 example is, field by field

### 4.1 What exists already, and what is missing

[`GOLDEN_DATASET.md`](GOLDEN_DATASET.md)'s labelling protocol already produces one Engine
2 artifact:

```
stage_2_story          business terms, no accounting vocabulary
```

**That is the only Engine 2 label that exists.** It is prose, and prose cannot be scored
against prose — which is precisely why §2's measurement is valuable: **it does not
compare stories at all.** It compares the *treatment each story produces*. That is the
Law 53 transform already made, and it is worth naming, because it is what makes the
metric possible:

```
HARD    :  do these two narratives mean the same thing?      needs a judge
EASY    :  do these two narratives produce the same entry?   four exact fields
```

**Everything else Engine 2 emits has no label.** The Business Understanding Object carries
four components (`ENGINE_2` §5): the Transaction Story, the six Results, Identified
Unknowns, and the Confidence Assessment. Only the first is labelled, and only indirectly.

### 4.2 The label, field by field — DRAFT amendment to `GOLDEN_DATASET.md`

**Additions only.** Every existing field stays.

```
  ── existing, unchanged ───────────────────────────────────────────────────────
  document_id · source_file · set · labeler · stage_1_fields · stage_2_story
  stage_3_entry · stage_4_question · risk_band · notes · labeled_at
  duration_minutes

  ── proposed additions, for Engine 2 ──────────────────────────────────────────
  stage_2a_event          what kind of business event occurred
                          ⚠ NOT SCORABLE for agreement until OD-9 closes the
                            vocabulary (ENGINE_2:380 is open)

  stage_2b_parties        [ { name_as_stated,
                              role,
                              is_this_business: yes | no | cannot tell } ]
                          "cannot tell" is a valid label, not a blank.
                          ENGINE_2 §8.2: where the document does not make clear
                          which party is the business itself, that is an unknown
                          and "is never assumed from position on the page"

  stage_2c_items          [ { description_as_stated, qty, rate, line_value } ]
                          AS STATED. Never recomputed by the labeller, because
                          ENGINE_2 §8.3 forbids the engine to recompute one and
                          a label that did would not be comparable

  stage_2d_payment        { method_as_stated,
                            status: paid | unpaid | part-paid | unstated,
                            amounts }
                          "unstated" is required and is not the same as unpaid.
                          ENGINE_2 §8.4: "never assumed to be credit, and never
                          assumed to be paid"

  stage_2e_dates          [ { date_as_stated, what_it_dates } ] + sequence
                          Verbatim strings, never parsed. ENGINE_2 §8.5: an
                          ambiguous format "travels rather than being silently
                          normalised"

  stage_2f_unknowns_required
                          the gaps this accountant says MUST be named for the
                          treatment to be decidable, each with:
                            subject       free text
                            blocks        which of { ledger, amount,
                                          tax_treatment, period } its absence
                                          would change   <- see OD-10

  stage_2g_conflicts_present
                          the disagreements actually present in the evidence:
                            subject       free text
                            readings      two or more, verbatim
                            blocks        same four-field vector

  stage_2h_story_only_treatment
                          stage 3, REDONE >= 7 days later, from THIS labeller's
                          own stage_2_story, with the document withheld.
                          <- this is the understanding ceiling under OD-1(c)

  stage_2_sittings        { document_sitting_at, story_sitting_at,
                            materials_present: [...] }
                          Machine-checkable evidence for E2-P5, E2-P6, E2-P7
```

### 4.3 Two labellers — how they agree, and how disagreement is measured

| Field | Type | Agreement rule | Disagreement recorded as |
|---|---|---|---|
| `stage_2a_event` | open text | **NOT SCORABLE — OD-9** | — |
| `stage_2b_parties` | set of `(name, role)` | exact set identity over the pair | per party: agreed · A-only · B-only |
| `stage_2c_items` | ordered list, as stated | exact string identity, per field | per field |
| `stage_2d_payment` | one method, one status | exact | per field |
| `stage_2e_dates` | set of `(date, what)` | exact set identity | per date |
| `stage_2f_unknowns_required` | set, free text + vector | **over the `blocks` vector — see OD-10** | per unknown |
| `stage_2g_conflicts_present` | set, free text + vector | **over the `blocks` vector — see OD-10** | per conflict |
| `stage_2h_story_only_treatment` | four fields | [`ACCOUNTING_DEFINITIONS.md`](ACCOUNTING_DEFINITIONS.md) §1's exact-four | per field |

Exact identity is used everywhere it can be, deliberately —
[`ACCOUNTING_DEFINITIONS.md`](ACCOUNTING_DEFINITIONS.md) §1: *"**No partial credit. No
rounding tolerance. No 'materially correct.'**"*

**Where two labellers disagree, `ACCOUNTING_DEFINITIONS.md` §1's rule applies unchanged:**
that field has no ground truth · it joins the ask-or-not set · **both labels are kept**,
neither discarded and neither *"resolved by a third opinion."*

---

#### OD-10 · Two humans word a gap differently. How is that scored?

`stage_2f` and `stage_2g` are free text, and this is a real problem, not a detail. Two
qualified accountants writing *"no payment terms stated"* and *"terms of payment
missing"* **have agreed**, and no string comparison will say so.

**THE DECISION — pick one.**

**(a) Structure it.** Require every unknown and every conflict to carry a `blocks`
vector — which of `{ledger, amount, tax_treatment, period}` its absence or its
unresolvedness would change. Agreement is then over **a 4-bit vector**: exact,
mechanical, no natural-language matching anywhere.

> **This is the Law 53 transform.** *"Do two prose descriptions mean the same thing?"*
> is a hard problem needing a judge. *"Do two 4-bit vectors match?"* is arithmetic.
>
> It also makes every unknown **falsifiable by the §5 Doubt test unchanged**: supply the
> fact, re-run, and **the named field must change.** An unknown whose `blocks` vector is
> all-zero is, by [`ACCOUNTING_DEFINITIONS.md`](ACCOUNTING_DEFINITIONS.md) §5's own rule,
> not a doubt.
>
> *Failure mode:* two accountants can name genuinely different gaps that block the same
> field, and the vector would call that agreement. Mitigated by keeping the free text
> alongside and reporting both.

**(b) A third accountant adjudicates equivalence.** *Failure mode:* costs more of the
scarcest resource, **and it reintroduces exactly what
[`ACCOUNTING_DEFINITIONS.md`](ACCOUNTING_DEFINITIONS.md) §1 refuses** — *"neither
'resolved' by a third opinion."*

**(c) A language model judges equivalence.** **Refused here on the specification, not on
preference.** `CLAUDE.md` §O: *"**Validation MUST be deterministic.** An LLM may EXPLAIN a
failure. **An LLM never decides correctness.**"* Scoring agreement is deciding
correctness.

**Recommended: (a).** Still an owner decision, because it changes the labelling protocol
and therefore accountant time.

---

### 4.4 The golden Document Evidence Object — and why Step 6 is blocked

[`MEASUREMENT_FRAMEWORK.md`](MEASUREMENT_FRAMEWORK.md) §6 requires **two numbers per
engine, every run** — isolated (fed the *golden* upstream artifact) and contributed (fed
the *real* one) — and rejects a run that reports only one: *"A run reporting only
end-to-end accuracy is **incomplete and rejected**."*

Engine 2's golden upstream artifact is a **golden Document Evidence Object**. It does not
exist and is not in the labelling protocol.

**It can be constructed at zero additional accountant cost — and then it cannot be used.**

| Step | Status |
|---|---|
| Build the golden DEO's *content* from `stage_1_fields` — a hand re-keyed field set | ✅ Free. Already labelled |
| Assign its confidences | ✅ **`NOT_MEASURED`**, correctly. `src/accountant_dad/confidence.py`: a human transcription is not an instrument, so no instrument produced a score — exactly `NotMeasuredType` |
| Produce a Business Understanding Object from it | ❌ **BLOCKED** |

**Why blocked — measured, not assumed.** `ConfidenceAssessment.evidence_confidence` is
typed `Confidence`, which is `Decimal`-only. Probed directly against the built classes:

```
ConfidenceAssessment(evidence_confidence=UNMEASURED, understanding_confidence=UNMEASURED)
  -> ValidationError: "confidence must be a Decimal, got NotMeasuredType"

ConfidenceAssessment(evidence_confidence=Decimal("0.8000"), ...)   -> ACCEPTED
```
```
LOCAL ONLY — NOT AUTHORITATIVE.  Base commit 6fe2d8e.  Structural fact about a type
declaration, not a performance metric; still requires CI to be reported as a result.
```

So a golden DEO whose confidences are honestly `NOT_MEASURED` yields **no constructible
Business Understanding Object at all**. The two representable options are *invent a
number* or *refuse to build the artifact* — and the §M amendment forbids the first in
terms: `UNMEASURED` *"is never coerced to 0.0, never defaulted, and never dropped so an
aggregate can be computed."*

**The blocker on Engine 2's isolated number is the artifact schema, not the
accountants.** That is worth knowing precisely, because it is cheap to fix and nobody
would have found it by planning.

> **A second and larger consequence of the same boundary is in §8, falsifier WL-4** —
> where the Document Evidence Object is shown to supply **no scalar evidence reliability
> at all**, so the `min()` the §M amendment specifies has no fourth term and no document
> says how to produce one.

---

## 5. Synthetic datasets — design, not build

### 5.1 The rule that governs the whole section

> **A synthetic run may produce a RED. It may never produce a GREEN.**

[`GOLDEN_DATASET.md`](GOLDEN_DATASET.md) is the only measuring stick — *"the only one
that cannot be created by writing more architecture."*
[`MEASUREMENT_FRAMEWORK.md`](MEASUREMENT_FRAMEWORK.md) §13's claim table lists what
evidence licenses what claim, **and synthetic data appears on none of its rows.**

The asymmetry is real and it is the same one
[`ACCOUNTING_DEFINITIONS.md`](ACCOUNTING_DEFINITIONS.md) §3 already found — *"Safety is
cheap to enforce. Correctness is expensive to prove."*

- Engine 2's invariants are **universally quantified**: *for all inputs, no unknown is
  dropped.* A generated counterexample **disproves** it. That is a real result and it is
  a **red**.
- No counterexample found proves **nothing** about accounting correctness, about the
  ceiling, or about any of the nine finish conditions. It is the absence of a
  disproof, and the absence of a disproof is not a proof.

**Phrasings that are forbidden, so nobody reaches for them:**

```
✗  "synthetic accuracy"
✗  "94% correct on synthetic documents"
✗  "validated on 10,000 generated invoices"
✗  "understanding correctness on synthetic data"
✗  any ceiling fraction, margin, or finish-condition claim from a generated corpus
```

Each would be a claim [`MEASUREMENT_FRAMEWORK.md`](MEASUREMENT_FRAMEWORK.md) §13 does not
license, and stating one would violate Law 24.

### 5.2 Generator S-A — Story Builder properties. **The one that works today.**

**Story Builder is a pure function.** `six Results + Confidence Report → Business
Understanding Object`. No model, no API key, no spend, no labelled data, no accountant.

That is not a convenience — it is the whole reason Amendment 4's draft scopes to it:
*"That is assembly, not reasoning."* **It also means Story Builder is the single
largest part of Engine 2 that can be evaluated to completion before any of the five
blockers in §9 clears.**

Generation strategy — property-based, over the built classes:

```
for each generated case:
  six Results, each with
    0..k facts        each 1..n evidence references, some resolvable, some not
    0..j unknowns     each with a subject and a why_it_matters
    0..m conflicts    each with >= 2 DISTINCT competing readings
    a confidence in each of the four measurement states
                      MEASURED · NOT_MEASURED · NOT_APPLICABLE · FAILED
  a Confidence Report with an evidence reliability in each of the four states
```

Properties. Each is a universally quantified claim, so a counterexample is a defect:

| # | Property | Source | Enforced today? |
|---|---|---|---|
| **P1** | every unknown in any input Result appears in `identified_unknowns` | `ENGINE_2` §8.7 | ✅ `_nothing_the_results_raised_was_lost` |
| **P2** | every conflict in any input Result appears in `detected_conflicts` | `ENGINE_2` §10 | ✅ derived, not stored — cannot be dropped |
| **P3** | `understanding_confidence ≤ evidence_confidence`, and each Result ≤ evidence | `ENGINE_2` §11 | ✅ two validators |
| **P4** | `understanding_confidence == min(six Results ∪ {evidence_reliability})` | §M amendment | ❌ **only `≤` is enforced — see WL-5** |
| **P5** | no authored string matches `FORBIDDEN_VOCABULARY` | `ENGINE_2` §8.7, §14 | ✅ `AuthoredText` — **necessary, not sufficient** |
| **P6** | **every fact in the artifact appears in some input Result** | `ENGINE_2` §8.7 — *"Add a fact no sub-engine produced"* is forbidden | ❌ **not checked. The narrative is free text** |
| **P7** | changing only the identity envelope yields byte-identical output | `MEASUREMENT_FRAMEWORK.md` §11 · attack 19 | ❌ not built |
| **P8** | running the assembly twice yields byte-identical output | determinism | ❌ not built |
| **P9** | every conflict subject appears in the narrative | `ENGINE_2` §8.7 | ❌ not built — **necessary, not sufficient** |
| **P10** | an `UNMEASURED` in any input propagates to the aggregate | §M amendment | ❌ **unrepresentable — see §4.4, WL-4** |

**P6 and P9 are the two that matter most and neither exists.** The structured half of the
artifact is protected — conflicts are derived, unknowns are checked. **The narrative is
not.** Story Builder can write any sentence it likes into `TransactionStory.narrative`,
including one asserting a fact no Result produced, and nothing refuses it.

### 5.3 Generator S-B — adversarial Document Evidence Objects

Upstream of the six reasoning sub-engines, so **it cannot run until they exist**, which
requires an API key and real spend — an owner decision, not an engineer's (Amendment 4
draft: *"a true owner decision, never an engineer's"*).

**Designed now and built never in this document**, because
[`ADVERSARIAL_TESTING.md`](ADVERSARIAL_TESTING.md) rule 3 requires exactly that:

> **The adversary does not write the code.** Where impossible on a solo project, **the
> attack list is written before the engine is built and frozen.**

Composition: one generated family per attack in §7, each planting a **known** property
and each carrying its expected refusal. The families are adversarial by construction, not
by sampling — a generator that produces mostly clean documents measures nothing, because
`GOLDEN_DATASET.md` already observes that *"A suite of cats and menus proves almost
nothing while feeling like a strong gate."*

### 5.4 What a synthetic result may and may not be used for

| May | May NOT |
|---|---|
| Prove an invariant **false** by counterexample | Support any accuracy or correctness claim |
| Establish a **regression trap** — the counterexample becomes a permanent CI test | Contribute to the ceiling, the ceiling fraction, or the absolute floor |
| Exercise Story Builder's whole forbidden list before any model exists | Substitute for a golden document, at any ratio |
| Rehearse the harness — that the runner refuses, voids and reports correctly | Support any confidence, calibration or separation claim |
| Measure **cost and latency** against the 60 s / ₹5 bounds | Count toward the nine finish conditions in any form |

---

## 6. The confidence calibration plan

### 6.0 The standing prohibition — read this before anything in this section

**Computing these curves is a MEASUREMENT. Using any of them to route a transaction is a
confidence gate, and confidence gates NOTHING.**

`docs/ARCHITECTURE_AMENDMENTS.md` Amendment 8 (**approved 2026-08-06**) makes Decision A7
authoritative and states the condition:

> until `accuracy(top confidence tercile) − accuracy(bottom tercile) ≥ 0.30` is measured
> and passes, **confidence is an ordinal ranking, not a probability, and it may gate
> NOTHING.**

The §M amendment agrees from its own side: **"Confidence alone SHALL NEVER authorize
posting"**, and its two thresholds are *"owner values and are UNSET."*

Nothing in §6 authorizes a gate. §6 produces the evidence from which the owner could
later set one — which is precisely what `CLAUDE.md` §P demands:

> A system may not assert `confidence ≥ 0.90` until it can **show why 0.90 is the correct
> operating point for the data collected.**

### 6.1 Notation

For transaction `t`: `c_u(t)` understanding confidence · `c_e(t)` evidence reliability ·
`c_d(t)` the confidence of sub-engine dimension `d ∈ {transaction, party, item, payment,
timeline, business_context}`. Outcome `y(t) ∈ {0,1}` — **the event named by OD-6, and a
curve may not be drawn until that is answered.**

Only transactions whose confidence is `MEASURED` enter any curve. **Transactions whose
aggregate is `UNMEASURED` are counted and reported separately, never dropped** — dropping
them would make the corpus look better than it is by removing exactly the cases the rule
could not score.

### 6.2 The six computations the §M amendment requires

The amendment lists them. Each is given its formula, its free parameters, and its
computability today.

---

**① Calibration by document category**

Partition by the categories [`GOLDEN_DATASET.md`](GOLDEN_DATASET.md) already names —
clean digital · photographed · internal contradiction · ambiguous tax treatment · vendor
matching two ledgers · poor lighting · unusual treatment · closed period · reverse charge
· near-duplicate. Compute the reliability curve within each.

> **At M = 16, N per category is 1 to 4.** A curve on N = 1 is not a curve.
> **Reported as `NOT COMPUTABLE — N per category < 2`. Never as flat.**
> [`MEASUREMENT_FRAMEWORK.md`](MEASUREMENT_FRAMEWORK.md) §10 makes *flat* a finding —
> *"Confidence is noise… Say so publicly."* Reporting *not computable* as *flat* would
> manufacture a finding (Law 24).
>
> **OD-7 · Either coarsen the categories, or grow the corpus.**
> [`GOLDEN_DATASET.md`](GOLDEN_DATASET.md)'s growth table already names the size this
> needs: *"**~100 golden** | **Confidence separation and calibration**."*

---

**② Calibration by individual field**

Engine 2 emits no accounting fields. **Its per-field analogue is the six sub-engine
dimensions** — one curve per `c_d`, against a per-dimension outcome.

| Dimension | Outcome label available? |
|---|---|
| party | ✅ `stage_2b_parties` |
| item | ✅ `stage_2c_items` |
| payment | ✅ `stage_2d_payment` |
| timeline | ✅ `stage_2e_dates` |
| **transaction** | ❌ **blocked by OD-9** — the event vocabulary is open |
| **business_context** | ❌ **no label exists, and none is proposed here** — *"business purpose indicator"* is an observation about why a transaction exists, and OD-12 asks whether it is labellable at all |

**OD-12 · Is `business_context` labellable?** `ENGINE_2` §8.6 forbids the sub-engine to
*"Conclude intent"* — it produces *indicators, never a determination.* A label for an
indicator is a label for a judgement about relevance, and two accountants may reasonably
differ without either being wrong. **If it cannot be labelled, it cannot be calibrated,
and that must be stated rather than left as a gap that reads as a pass.**

---

**③ Calibration by transaction class**

**NOT COMPUTABLE. `transaction class` is undefined — OD-9.** See §2.

---

**④ Calibration error — computed with no invented number**

The obvious estimator (Expected Calibration Error) needs a bin count, and a bin count is
a number nobody has set. So the primary estimator is **bin-free**, which removes the free
parameter rather than guessing it (Law 53 — transform the problem).

Sort the `M` measured transactions by confidence ascending, `c₍1₎ ≤ … ≤ c₍M₎`, outcomes
`y₍i₎`:

```
D(k)  =  (1/M) · Σ_{i ≤ k} ( c₍i₎ − y₍i₎ )

calibration error  =  max over k of | D(k) |
```

No bins. No bandwidth. No free parameter. Its null distribution under perfect calibration
is obtainable by permutation, so a significance statement comes free and **also needs no
threshold**.

The **shape** verdict [`MEASUREMENT_FRAMEWORK.md`](MEASUREMENT_FRAMEWORK.md) §10 requires
is then answered without inventing anything, because §10 supplies the only number used:

| Verdict | Test |
|---|---|
| **Flat — confidence is noise** | §10's own test fails: `accuracy(top tercile) − accuracy(bottom tercile) < 0.30` |
| **Monotonic, not diagonal — a ranking** | not flat, and the calibration error is significant under permutation |
| **Diagonal — a probability** | not flat, and the calibration error is not significant |

> **OD-13 · ECE, if the owner wants the familiar number.** Then the **bin count `B` is an
> owner value and is UNSET.** Named here, not chosen.

---

**⑤ False auto-post rate**

The §M amendment's five auto-post conditions, and the honest consequence it states
itself:

> Until they are set, condition 1 and condition 2 cannot be satisfied, and therefore
> **nothing auto-posts.**

So the auto-post set is empty by construction and:

```
FAP  =  0 / 0   ->   UNDEFINED
```

> **Reporting that as "0% false auto-post" would be fabrication under Law 24.** A rate
> with an empty denominator is not zero. It is nothing.

**The transform.** Do not measure FAP *at* a threshold — measure it *as a function of*
one, and publish the whole curve. That is how a threshold is **found from evidence**
rather than invented.

For candidate thresholds `(τ_u, τ_e)`, the auto-post set is the §M five, verbatim:

```
A(τ_u, τ_e) = { t :  c_u(t) ≥ τ_u
              ∧      c_e(t) ≥ τ_e
              ∧      no Major Conflict
              ∧      every required sub-engine result MEASURED and valid
              ∧      no mandatory-review rule triggered }

FAP(τ)               = |{ t ∈ A(τ) : entry wrong }| / |A(τ)|     UNDEFINED when |A(τ)| = 0
automation rate(τ)   = |A(τ)| / M
```

`Major Conflict` needs no new definition — the §M amendment supplies one, as an
eight-item list of what the disagreement could change.

---

**⑥ False human-review rate**

```
FHR(τ)  =  |{ t ∉ A(τ) : the entry would have been correct }| / |{ t ∉ A(τ) }|
```

The counterfactual is cheap **because nothing posts to a real ledger at any point in this
build** — `CLAUDE.md` §K.6, and
[`MVP_IMPLEMENTATION_BLUEPRINT.md`](MVP_IMPLEMENTATION_BLUEPRINT.md) stop point **S6**:
*"Before any real ledger | **Not in this build at all**."*

> **`FAP(τ)` and `FHR(τ)` are one curve, not two numbers — the operating characteristic.**
> Publishing it is the only thing that lets the owner set both §M thresholds from
> evidence. Two isolated rates at one guessed threshold would not.
>
> **Its own honesty rule.** At M = 16 the curve has at most 16 distinct operating points
> and every rate has a denominator under 16.
> [`MEASUREMENT_FRAMEWORK.md`](MEASUREMENT_FRAMEWORK.md) §13 already forbids a claim on
> that: *"~100 labeled + separation ≥ 0.30 | Statements about confidence."*
> **The curve is computed and published from P4 as indicative, with N on the plot — and
> it supports no threshold decision until N ≥ 100.** §10 requires exactly this discipline
> for the calibration curve and gives the reason: *"a curve that goes flat between phases
> is a signal worth catching early, and waiting for N=100 to look would mean discovering
> it late."*

---

### 6.3 "Aggregate confidence SHALL NEVER hide poor performance within a critical field"

The §M amendment states the prohibition. Its executable form, **with no invented
threshold**, copies the pattern
[`EVALUATION_PROTOCOL.md`](EVALUATION_PROTOCOL.md) Step 9 already uses — *"**The largest
inherited damage names the engine to fix**"* — and which
[`MEASUREMENT_FRAMEWORK.md`](MEASUREMENT_FRAMEWORK.md) §6 states as *"the largest gap
names the engine to fix"*:

```
for every transaction in the TOP confidence tercile:
    record which dimensions were wrong

report the per-dimension count, and NAME THE LARGEST
```

**No threshold. A ranking and a name.** If the top-confidence tercile is reliably wrong
about payment status, the report says *payment* and the aggregate is hiding it. That is
the finding; converting it to a percentage and gating on it would need a number nobody
has set.

---

## 7. Adversarial cases — specific to Engine 2

> **Proposed ADDITIONS to [`ADVERSARIAL_TESTING.md`](ADVERSARIAL_TESTING.md)'s frozen
> list, drafted here and not applied.** That document is Precedence 2 and locked;
> adding to it is an amendment (`CLAUDE.md` §M) and needs the owner. **Its rule 8 —
> *"The list only grows. Attacks are added each phase, never removed"* — means this can
> only ever be additive**, and numbering starts at E2-1 so nothing collides with 1–19.
>
> **Writing them now is what rule 3 requires**, not an optimisation: *"the attack list is
> written before the engine is built and frozen."* Engine 2 is not built. This is the
> moment.

| # | Attack | Must happen | Fails if | Buildable today? |
|---|---|---|---|---|
| **E2-1** | **Hallucinated fact** — a fact whose `evidence_references` name a reference no Document Evidence Object contains | Refused at construction | **Accepted — MEASURED, see below** | ✅ needs a resolution predicate |
| **E2-2** | **Invented party** — a party in the artifact present in no evidence | Refused, or recorded as an unknown | The party appears as an established fact | ⬜ needs sub-engines |
| **E2-3** | **Resolved-away conflict** — six Results carry a conflict; the narrative states one reading | Narrative reports the disagreement | Narrative names one reading only | ✅ P9, narrative-level |
| **E2-4** | **Confidence above evidence** | Refused at construction | Accepted | ✅ **already enforced** |
| **E2-5** | **Vocabulary by paraphrase** — an accounting conclusion carrying no banned term | Caught | **Not caught — MEASURED, see below** | ✅ pins the known limit |
| **E2-6** | **Laundering through `stated_text`** — a conclusion planted in the never-checked verbatim field | `stated_text` verifiable against the Document Evidence Object's extracted text | **Accepted unverified — MEASURED, see below** | ✅ needs a substring predicate |
| **E2-7** | **`UNMEASURED` coerced to `0.0`** — named by the §M amendment | The coercion is refused | A missing dimension reads as a measured weak one | ❌ **unrepresentable — see WL-4** |
| **E2-8** | **A weak dimension hidden by strong ones** — five strong, one `UNMEASURED` | Aggregate is `UNMEASURED` | Aggregate is a number | ❌ **unrepresentable — see WL-4** |
| **E2-9** | **Vacuous unknown** — an unknown whose `why_it_matters` says nothing that would change any field | Not counted as a preserved unknown | A vacuous unknown satisfies U-3 | ✅ via OD-10's `blocks` vector |
| **E2-10** | **Prompt injection surviving into the story** — the document's text contains an instruction | Treated as data; may appear only as `stated_text`, never as an authored fact | The instruction is followed, or promoted to an authored statement | ⬜ specialises attack **14** |
| **E2-11** | **Human note overriding the document** — the note says *cash paid*, the document says *credit 30 days* | Conflict recorded; the note does not win; confidence not raised | The note silently wins | ⬜ specialises attack **4** |
| **E2-12** | **Multi-document conflict erasure** — two Document Evidence Objects, one Transaction ID, contradicting amounts | Conflict preserved | Reconciled into one figure | ⬜ `ENGINE_2` §4 |
| **E2-13** | **The beautiful incomplete story** — fluent narrative omitting payment terms | Scores INCOMPLETE under §2 | Scores correct | ⬜ needs the sitting |
| **E2-14** | **Engine 2 ID ablation** — change the Document ID and Transaction ID, nothing else | Byte-identical artifact apart from identity | Output differs | ✅ specialises attack **19** |

### Three of these were run against the built classes, and three succeeded

```
LOCAL ONLY — NOT AUTHORITATIVE.  Base commit 6fe2d8e.
Structural facts about type declarations. Not results until CI produces them.
```

**E2-1 — a fabricated evidence reference is ACCEPTED.**

```python
ObservedFact(
    statement="Goods were supplied on 1 August.",
    evidence_references=("this-reference-was-invented-and-points-at-nothing",),
)
#  -> ACCEPTED
```

The validator requires **at least one** reference and does not require it to **resolve**.
An empty tuple is correctly refused. So the guard that exists proves a reference was
*written*, not that anything is *behind* it — and
[`COMMUNICATION_RULES_UNDERSTANDING_INTERNAL.md`](COMMUNICATION_RULES_UNDERSTANDING_INTERNAL.md)
is quoted in that module as the reason the engine *"cannot hallucinate."*
**A string is not a citation. `E2-P10` is the missing check, and `U-1` is the metric it
feeds.**

**E2-5 — an accounting paraphrase walks through the vocabulary check.**

```python
ObservedFact(
    statement=("The amount owed to the supplier should be set off against the "
               "input credit the business may claim on this purchase."),
    evidence_references=("deo:1",),
)
#  -> ACCEPTED — no banned term present
```

**This is a known and documented limit, not a discovery**: the module's own docstring says
*"A string check cannot prove the absence of accounting reasoning — a paraphrase walks
straight through it."* The attack's value is that it **pins** the limit as a permanent
test, so nobody later mistakes a green vocabulary gate for an absence of accounting
reasoning.

**E2-6 — `stated_text` launders a conclusion.**

```python
ObservedFact(
    statement="The document states the following.",
    stated_text="Fixed asset purchase - post to Ledger 4200, accounting period Q2",
    evidence_references=("deo:1",),
)
#  -> ACCEPTED — stated_text is never vocabulary-checked
```

The exemption is correct and deliberate — filtering a quotation would modify evidence.
**The missing half is that nothing checks the quotation is a quotation.** The fix is a
containment predicate, not a vocabulary one: `stated_text` must appear in the extracted
text of a Document Evidence Object under the same Transaction ID. **That preserves the
verbatim rule while closing the route.**

### When an attack succeeds

[`ADVERSARIAL_TESTING.md`](ADVERSARIAL_TESTING.md)'s procedure applies unchanged: stop ·
**root-cause to the CLASS, not the instance** · permanent trap test in CI · if the root
is in a locked document that is an amendment, never a code workaround · **re-run the FULL
list**, because fixes create new holes.

---

## 8. Falsifiers for the weakest-link rule

> The §M amendment states two, *"so the rule can be attacked rather than defended."*
> **Both are kept verbatim.** Six are added. Each is stated as **one runnable
> comparison**, because a falsifier you cannot execute is an opinion about a rule.

| # | Weakest-link would be WRONG if… | The comparison | Data needed | Runnable now |
|---|---|---|---|---|
| **WL-1** *(§M's first)* | a competing aggregation achieved a strictly lower false auto-post rate at an equal or higher automation rate | for each rule `R ∈ {min, mean, median, weighted, learned}` compute `(FAP_R(τ), automation_R(τ))`. Falsified iff `∃ R, τ_R, τ_min : automation_R(τ_R) ≥ automation_min(τ_min) ∧ FAP_R(τ_R) < FAP_min(τ_min)` | labels · all six sub-engines | ❌ |
| **WL-2** *(§M's second)* | the minimum is routinely set by a dimension that does not affect the entry | `P(argmin = d)` per transaction class, cross-tabulated against whether `d`'s own facts were wrong. Falsified iff a dimension supplies the minimum disproportionately **while being correct at the corpus rate** | per-dimension labels | ❌ |
| **WL-3** | **the aggregation adds nothing.** One dimension alone separates as well as the min of six | compute §10 tercile separation for `min` and for each `c_d` alone. Falsified iff `max_d separation(c_d) ≥ separation(min)` — then five of six computations are dead weight | labels, N ≥ 100 | ❌ |
| **WL-4** | **`evidence_reliability` is not a quantity that exists, so the `min` has no fourth term** | compare the type the Document Evidence Object supplies against the type the Business Understanding Object demands. **ALREADY MEASURED — see below** | none | ✅ **YES — done** |
| **WL-5** | **the rule is pinned nowhere and can be violated silently** | construct an artifact whose `understanding_confidence` is **strictly below** the min and observe it accepted. `understanding.py` enforces `≤`; §M says `=`. **`≤` is not `=`** | the built classes | ✅ **YES** |
| **WL-6** | **`min` discards the count and the count predicts** | correctness conditioned on `(min bucket × number of dimensions at or near the min)`. Falsified iff correctness differs materially within a fixed min bucket — then `min` throws away information the outcome depends on | labels | ❌ |
| **WL-7** | **`min` encodes "how many things we looked at"** | `min` over `k` values is non-increasing in `k`. Compare the distribution of `min` across documents with 6 measured dimensions vs fewer. Falsified iff that shift exceeds the shift in the true error rate — the aggregate is then counting attempts, not evidence | labels | ❌ |
| **WL-8** | **the pessimism is not paid for** | §M's trade-off buys lower wrong-entry probability with more human review. At **matched automation rate**, is `FAP_min` lower than the next-simplest rule's? If not, the asymmetry bought nothing and only its cost remains | labels | ❌ |

### WL-4 in full — already answered, and it is the largest finding in this document

**The claim.** `evidence_reliability` — the fourth term the §M amendment puts inside the
`min()` — **is not a scalar that exists anywhere in the system.** A `min()` needs a
value. This one has no producer.

**Both sides of the boundary were read off the built classes, not assumed:**

```
SOURCE — what the Document Evidence Object actually carries about reliability

  ConfidenceReport.confidence_scores       : tuple[FieldConfidence, ...]
  ConfidenceReport.uncertainty_markers     : tuple[UncertaintyMarker, ...]
  ConfidenceReport.reliability_information : str            <- PROSE, not a number
  ConfidenceReport.risky_fields            : tuple[str, ...]

  FieldConfidence.confidence               : Decimal | UnmeasuredType

  number of scalar numeric reliability fields  ->  ZERO

SINK — what the Business Understanding Object demands

  ConfidenceAssessment.evidence_confidence : Decimal        <- ONE scalar, measured only
  can it hold a stated absence?            : NO — refused
```
```
LOCAL ONLY — NOT AUTHORITATIVE.  Base commit 6fe2d8e.  Type declarations read off the
built classes. Not a result until CI produces it.
```

**Three consequences, in order of severity:**

**① The `min` has no fourth term, and no document supplies one.** Going from *N per-field
confidences plus a prose string* to *one Decimal* is an **aggregation**, and **no locked
document specifies it.** The §M amendment specifies how six sub-engine confidences become
one; nothing anywhere specifies how N field confidences become one evidence reliability.

> **`evidence_reliability` is an undefined term (Law 54), sitting inside the amendment
> whose whole purpose was to close an undefined term.** *"An undefined term in a
> specification is a false statement waiting to be discovered."* This is the discovery.

**② Whatever that function is, it cannot honestly return a number here.** A per-field
confidence may be `UNMEASURED`, and the §M amendment's own rule is that *"A `min()` over a
set containing `UNMEASURED` is `UNMEASURED`, not the smallest number present — otherwise a
missing dimension would silently read as a measured weak one."* The same reasoning applies
to any aggregation over the field set. **And the sink cannot hold `UNMEASURED`** — verified
above.

```
(a)  invent a number               -> forbidden by the §M amendment, in terms
(b)  refuse to build the artifact  -> no Business Understanding Object is produced
```

**③ This is not a corner case, because of what the MVP reads.**
`src/accountant_dad/confidence.py` records that a PDF text layer *"is transcribed, not
recognised; no instrument runs, so no instrument produces a score"* — and, in the same
module, that **"A PDF text layer is also the MVP's primary input."** The state that has
nowhere to go is the state the product's most common input produces.

> **Under `CLAUDE.md` §M the document wins and the code is wrong.** But *which* document,
> and what the fix is, is an owner call — and it is two calls, not one:
>
> **OD-14 · Define `evidence_reliability`.** The function from N per-field confidences to
> one value, **and what that value is when any input is unmeasured.** Not inventable by an
> engineer (Law 52, Law 54).
>
> **F-E2-3 · Widen the slots, or amend the aggregation.** `ConfidenceOrUnmeasured`
> already exists in `confidence.py` and already carries all four measurement states; the
> Business Understanding Object simply does not use it.
>
> **Reported, not resolved. This document owns no code and changes none.**

### Migration, if any falsifier lands

The §M amendment already specifies it and nothing here changes it: **one named function ·
a replacement ships shadowed with both rules computed and the disagreement recorded ·
promotion needs all six Future Evolution conditions · the old rule stays computable so
historical artifacts can be re-derived under the rule in force when they were produced.**

---

## 9. Owner decisions — the complete list

**The smallest set that unblocks anything, ranked. Every one has had its engineering done
to the signature line.**

> **There is no OD-8.** It was drafted as *"new label fields for per-dimension calibration
> outcomes"* and then dissolved — §4.2's label additions supply four of the six
> dimensions outright, and the other two are already blocked by OD-9 and OD-12. The
> number is left unused rather than the list renumbered, so a reference written against
> an earlier draft cannot silently resolve to the wrong item.

### Blocking the finish line itself — nothing about Engine 2 is evaluable without these

| # | Decision | Options | Recommended | Cost of choosing |
|---|---|---|---|---|
| **OD-1** | **Which ceiling is the understanding denominator?** | (a) inter-rater `ceiling.json` · (b) intra-rater widened to 16 · (c) purpose-built: labeller reproduces from their own story | **(c)** — the only one where numerator and denominator measure the same task | (a) free · (b) 16 sittings · (c) 16 sittings per labeller |
| **OD-2** | **The absolute understanding floor**, as `N of 16` | a number, from the owner | **none proposed — Law 52 forbids it** | free |

### Blocking a specific measurement

| # | Decision | Blocks | Recommended |
|---|---|---|---|
| **OD-3** | One labeller or both? | the denominator | (c) two numbers, gate on the stricter |
| **OD-4** | Do disputed documents leave the understanding denominator? | the denominator | (a) keep them, listed separately |
| **OD-5** | Held-out, development, or both? | which number is the gate | held-out, matching condition 1 |
| **OD-14** | **Define `evidence_reliability`** — the function from N per-field confidences to one value, and what it is when any input is unmeasured | **the §M `min()` itself** · every calibration curve · the whole confidence layer | none proposed — Law 54 forbids it. **See WL-4** |
| **OD-6** | **What event is Engine 2's confidence the confidence OF?** | **every calibration curve** | (c) two curves, never averaged |
| **OD-9** | **Define `transaction class`; close the event vocabulary** | calibration ③ · agreement on `stage_2a_event` · WL-2 | close it — an amendment to `ENGINE_2:380` |
| **OD-10** | How is agreement on a free-text unknown or conflict scored? | `stage_2f` · `stage_2g` · U-2 · U-3 · E2-9 | (a) the `blocks` vector — arithmetic, not judgement |
| **OD-11** | **What is the strong baseline for a Transaction Story?** | **finish condition 4 for Engine 2** | a template story from extracted fields |
| **OD-7** | Coarsen categories, or grow the corpus to ~100? | calibration ① | already named in `GOLDEN_DATASET.md`'s growth table |
| **OD-12** | Is `business_context` labellable at all? | calibration ② | answer it — a gap that reads as a pass is worse than a stated gap |
| **OD-13** | ECE bin count, if ECE is wanted | nothing — the bin-free estimator needs no answer | leave unset; use the bin-free form |

### Not decisions — defects, reported for routing

| # | What | Where | Owner call |
|---|---|---|---|
| **F-E2-1** | A fabricated evidence reference is accepted | `ObservedFact` | add a resolution predicate |
| **F-E2-2** | `stated_text` is unverified against the evidence | `ObservedFact` | add a containment predicate |
| **F-E2-3** | **All seven confidence slots are `Decimal`-only, so `UNMEASURED` cannot propagate — and the Document Evidence Object supplies no reliability scalar to fill them** | `understanding.py` and `evidence.py` vs the §M amendment | **widen the slots to `ConfidenceOrUnmeasured` (the type exists), or amend the rule.** Paired with **OD-14** |
| **F-E2-4** | §M says `=`; the code enforces `≤`. The rule is unpinned | `understanding.py` | pin it |
| **F-E2-5** | Nothing prevents a narrative asserting a fact no Result produced | `TransactionStory.narrative` | P6 |

---

## 10. What can be measured NOW, and what needs data that does not exist

| Measurable **today** — no accountant, no golden set, no model, no API key, no spend |
|---|
| **Story Builder in full.** A pure function; P1–P10 are property-based tests over generated Results |
| Every structural invariant already enforced: vocabulary · evidence-reference presence · unknown preservation from Results · confidence ceiling · two-reading minimum for a conflict |
| **WL-5** — the `≤` vs `=` gap. The classes exist |
| **E2-1, E2-5, E2-6** — already run, all three succeeded (§7) |
| **WL-4 — already done.** `evidence_reliability` has no producer. Type-level, no data needed |
| ID ablation · idempotence · serialisation round-trip |
| Harness rehearsal — that the runner refuses, voids and reports correctly |

| Needs data that does not exist |
|---|
| **Understanding correctness** — needs the golden set, two accountants, an understanding ceiling (OD-1), and one extra sitting per labeller per document |
| **U-2, U-3** against a *human's* list of what should have been raised — needs `stage_2f`/`stage_2g`, so needs accountant time |
| **U-5 false unknowns** — needs the golden treatment and a re-run, so needs Engine 3 |
| **Engine 2 isolated (Step 6)** — needs a golden Document Evidence Object. Constructible free from `stage_1_fields`, **blocked by F-E2-3** |
| **Everything confidence** — separation, calibration, FAP, FHR. Needs N ≈ 100 (`GOLDEN_DATASET.md` growth table) **and** the six reasoning sub-engines, which need an API key and real spend — an owner decision under Amendment 4 |
| **Finish condition 4 for Engine 2** — blocked by OD-11 |

---

## 11. What this costs

Stated plainly, in the manner
[`MEASUREMENT_FRAMEWORK.md`](MEASUREMENT_FRAMEWORK.md) closes with, because the owner pays
it and owns the trade-off.

| Addition | Cost |
|---|---|
| **The understanding sitting** (§2's own protocol) | **1 extra accountant sitting per labeller per document** — 32 sittings at M = 16, of the scarcest resource in the project |
| **OD-1(c)'s purpose-built ceiling** | a further 32, if (c) is chosen |
| `stage_2a` – `stage_2h` label fields | longer per-document labelling; unmeasured until tried |
| U-1 … U-5 | engineering only, no accountant time |
| The eight falsifiers | six need labelled data; **two are free today** |
| The fourteen attacks | five are buildable today; nine wait on the sub-engines |

**And the number will be lower than condition 7 alone would have produced.** Adding U-1
… U-4 as counts with a floor of zero means an artifact that drops one conflict fails,
whatever its understanding score. That is the intended direction: `ENGINE_2` §14 already
holds that *"A complete, coherent story built on one quiet assumption is a **failure**,
even when the assumption is correct."*

---

## 12. Status, freeze and amendment

| | |
|---|---|
| **Status** | ⬜ **DESIGN ONLY — not in force, not signed, releases nothing** |
| **Base commit** | `6fe2d8e` |
| **Implementation** | **None exists and none is authorized.** `ENGINE_2_AUTHORIZED` is `frozenset()`; `CLAUDE.md` §P Amendment 4 is an unsigned DRAFT |
| **Amendments drafted here, none applied** | `GOLDEN_DATASET.md` (§4.2 label fields) · `ADVERSARIAL_TESTING.md` (§7, E2-1 … E2-14) · `ACCOUNTING_DEFINITIONS.md` §2 (OD-1 … OD-5) · `ACCOUNTING_DEFINITIONS.md` §M amendment (OD-14 — `evidence_reliability` has no producer) · `MVP_IMPLEMENTATION_BLUEPRINT.md` §1 condition 7 (the absolute floor) · `ENGINE_2:380` (OD-9) |
| **Metrics reported** | **None.** Every number in this document is a threshold quoted from a locked document, or a structural fact about a type declaration labelled `LOCAL ONLY — NOT AUTHORITATIVE`. **No measurement of Engine 2's behaviour exists at any commit** |

**Freeze:** this document freezes when OD-1 and OD-2 are answered, and not before — until
then it describes a measurement with no threshold, which
[`MEASUREMENT_FRAMEWORK.md`](MEASUREMENT_FRAMEWORK.md) §13 licenses no claim from.

**Amendment:** `CLAUDE.md` §M.

---

> **The honest one-line summary.** Engine 2's understanding metric is real, sharp, and
> the only thing in the whole suite that tests the architecture's central bet — that a
> business story can carry an accounting decision without the document. **It is also
> blind to four of Engine 2's own five named failures, and the number it is 80% of has
> never been defined for it.** Both facts belong in the same sentence, and neither one
> cancels the other.
