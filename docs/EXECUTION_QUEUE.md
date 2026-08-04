# Execution Queue

> **Precedence: none.** This document has **no authority.** It is a working queue that
> sequences work already specified elsewhere.
>
> Where this and any locked document disagree, **the locked document wins and this file
> is wrong.** Where this and `MVP_IMPLEMENTATION_BLUEPRINT.md` disagree, **the blueprint
> wins.** It exists so the order of work is visible, not to define the work.
>
> Written 2026-08-03.

---

## Why this exists

Twelve things blocked the MVP build. Four were decisions only the user could make. All four
were taken on 2026-08-03. This records what each decision was, what it unblocked, and what
gets built in what order because of it.

---

# Part 1 — The four decisions

## D1. Ground truth — public sources

**Decision.** Government e-invoice JSON schema, published GST rate tables, and ICAI /
GST-department worked examples. **No accountant, no payment, no waiting.**

### Why this works — the transform

The hard problem was *"get two qualified accountants to label 25 invoices."* The easier
equivalent problem is this:

> **A GST tax invoice is legally required to print its taxable value, rate, CGST/SGST/IGST
> split, total, date and supplier GSTIN.**

So of the four fields that `ACCOUNTING_DEFINITIONS.md §1` requires for **Correct**:

| Field | Where the answer comes from |
|---|---|
| **Amount** | On the document. Arithmetically self-checking |
| **Tax treatment** | On the document. Rate and split are printed and must reconcile |
| **Accounting period** | On the document. The invoice date |
| **Ledger** | **The only field needing judgement** |

**Three of four verify themselves.** The judgement problem shrinks to one field.

### What gets built

```
ingestion CLI              fetch, hash, record, refuse anything off the source list
provenance manifest        source URL · retrieval date · SHA-256 · licence, per file
PII scanner                real GSTIN / PAN / name / address → FLAGGED, NOT COMMITTED
negative controls N1–N9    proforma · PO · quotation · challan · duplicate · wrong
                           company · blanked amounts · blank page · unrelated photo
golden set loader          development 10 · held-out 6 · disputed set
pre-registration template  written and committed BEFORE any run
```

### Permitted sources — exhaustive

| Source | For |
|---|---|
| `gst.gov.in` · `cbic.gov.in` · `einvoice1.gst.gov.in` | e-invoice JSON schema, rate tables, published specimens |
| `icai.org` | guidance material, published formats |
| Other government / statutory portals | rate notifications, format specifications |
| Public invoice specimens and templates | golden-set candidates |

**Prohibited without separate approval:** anything behind a login, paywall or licence
agreement · executables · auto-running archives · installers · scraping at volume · any
source not listed above.

**Data only. Nothing downloaded is ever executed.**

### Two different things, never mixed

| | Standard applied |
|---|---|
| **Reference data** — rate tables, e-invoice schema | Knowledge Brain material. **Advisory, never binding** (INV-12) |
| **Golden-set documents** — the ~25 | Enter a **correctness denominator.** Held to a completely different standard |

### ⚠️ The limitation, recorded rather than buried

> **Internet-sourced documents are largely clean templates. Real intake is a WhatsApp
> photograph — skewed, blurred, cropped, partially shadowed.**
>
> **A golden set built from templates measures extraction on templates.**

This goes into the pre-registration under *what makes a run misleading*. **It is never
allowed to become true by omission that the system was "measured on real business
documents."**

**Synthetic documents may exist for pipeline testing only, tagged so they can never enter
a correctness denominator.** A generated document is never counted as real.

### Still the user's, never fabricated

**The human ceiling.** Not estimated, not inferred, not proceeded-as-if. Until it exists,
every number is reported **without a ceiling and explicitly weaker** — per
`MVP_IMPLEMENTATION_BLUEPRINT.md §5`.

---

## D2. Coverage floor 100% — and accuracy is not a threshold

**Decision.** Two metrics that never touch each other.

```
COVERAGE    "did the system reach a terminal state autonomously?"      TARGET 100%
            terminal = posted | Clarification Request | Rejected
            asking a human IS success.  HANGING is the only failure.

ACCURACY    "was the result correct?"                                  NO THRESHOLD
            enforced structurally, not by a number
```

### Why the split matters

Making the AI's *reasoning* error-free is not achievable. Making a wrong entry **impossible
to post** is. `ACCOUNTING_DEFINITIONS.md:139` already states the asymmetry:

> **Safety is cheap to enforce. Correctness is expensive to prove.**

Conditions 2, 3 and 4 of **Safe** are checkable by the conformance suite — no ground truth,
no accountant, no cost. Only condition 1 needs a human.

**So the floor is set on autonomy, where being wrong costs speed. Not on correctness, where
being wrong costs someone's books.**

**An incorrect entry must NEVER be silently accepted.** Insufficient confidence produces
`I don't know` or a Clarification Request — never a guess.

### The five structural safety gates

Machine-checkable. No accountant, no ground truth, no money. Every one runs on every commit.

| # | Gate | Rule | On failure |
|---|---|---|---|
| **1** | **Arithmetic** | `taxable × rate = tax` **and** `taxable + tax = total` | **REFUSE** |
| **2** | **Traceability** | every field resolves to a source region in the document | **REFUSE** |
| **3** | **Balance** | debit = credit, exact to the paisa | **REFUSE** |
| **4** | **Period** | closed accounting period detected **before** Tally is contacted | **REFUSE** |
| **5** | **Idempotency** | key = Decision ID + Decision Version + Destination | **cannot double-post** |

**Each ships with a canary that MUST be rejected.** A gate that exits 0 without examining
anything is hollow, and a hollow gate is worse than no gate — it manufactures trust.

### ⚠️ Consequence for finish condition 2

`MVP_IMPLEMENTATION_BLUEPRINT.md §1` condition 2 reads *"Absolute floor ≥ the floor agreed
at sign-off."* **The coverage decision replaces it, so condition 2 as written now carries no
value.** Flagged, not silently rewritten. It needs an amendment.

---

## D3. Tally — deferred, not blocking

**Decision.** Tally is an **external integration dependency, not a core dependency.**

### The transform

The hard problem was *"make GitHub's Linux runners drive Windows Tally software."* Tally
speaks **XML over HTTP**, so the real question splits:

```
(a) is our XML exactly right?   →  provable on Linux, free, EVERY commit
(b) does Tally accept it?       →  needs Tally ONCE per XML shape, not per run
```

**One authentic exported XML sample unblocks roughly 95% of development and testing.**

### Built now

```
published XML specification study     what the envelope actually is
envelope models                       request and response shapes
XML parser                            defensive — every file is hostile input
XML validator                         schema and structural conformance
canonical internal artifact           the shape our side owns
import pipeline · export pipeline
golden-XML byte comparison
conformance · golden · negative · adversarial tests that need no live instance
```

### Deferred to a **Live Tally Integration** milestone

```
1  end-to-end import into Tally
2  end-to-end export from Tally
3  live compatibility verification
4  performance measurement against a real instance
```

**These four may not block** the Brain, the Application Layer, any engine, the parser, the
validators, or the remaining CI gates.

### The design rule that makes this safe

> **Every Tally-facing component sits behind an interface, so replacing XML samples with a
> live instance later requires ZERO architectural change.**

Enforced by a conformance predicate: **no engine may import a Tally symbol.**

**Still frozen:** Tally *posting*. The transport gets built; it does not get wired.

---

## D4. LLM — free provider, pinned, behind an interface

**Decision.** A free internet API, version-pinned, swappable by one configuration value.

**Not blocking.** Nothing before P4 calls a model. Selection happens when P4 arrives, with a
recorded comparison: capability on real documents · free-tier rate limits · whether dated
version pins are honoured · cost per document against the ₹5 bound.

### ⚠️ The risk this design has to absorb

**Free tiers frequently do not honour version pins**, and `MVP_BUILD_VERIFY_FIX.md:68` is
explicit: *"An unpinned model makes every past number unreproducible."*

**Mitigation, built in from the start:** record the exact model string **and a SHA-256 of
every response** on every run. Provider drift is then detectable even when the pin silently
moves — which is what the drift canary in `MEASUREMENT_FRAMEWORK.md §9` exists to catch.

---

# Part 2 — CI enforcement repair

Found by audit 2026-08-03: **the workflows are well built and the enforcement is
disconnected.**

| | Fix | State |
|---|---|---|
| **A1** | A pull request could rewrite its own enforcer and pass its own check. Enforcement scripts now execute from the **base branch**, never the PR's checkout | PR #19 |
| **A2** | `tools/ci/` had no path attribution at all. `CODEOWNERS` added | PR #20 |
| **A3** | Nine placeholder gates: **implement**, or state the exact blocker in the step's own output. **No third option** | in progress |
| **A4** | §P said *"Merge gate exists and is PROVEN"* — true, and it binds nothing. **Exists ≠ binds** now recorded | PR #21 |

## The measured record

```
PR #4   merged 2026-08-02 19:34Z   every check red
PR #14  merged 2026-08-02 20:01Z   every check red
PR #15  merged 2026-08-02 20:32Z   6 required GREEN · 14 others RED · merged

ruleset created  19:32Z   required list DELIBERATELY EMPTY (documented bootstrap)
ruleset updated  21:35Z   six checks added
```

**All three merged before any check was required** — so they are not evidence that a
required check failed to hold. **The live hole is unchanged:** 6 of 23 bind, and PR #15 is
the exact shape that still merges today.

## `merge gate` promotion — the user's, later, and not yet

`merge gate` is the only job that polls every gate and demands all succeed. **One entry
would make all 23 bind.**

**It cannot be promoted today.** Nine gates `exit 1` by design; four cannot be implemented
until P1 and P2 produce artifacts. Requiring it now hard-locks the repository — including
against the pull request that would fix the placeholders.

```
implement and prove each gate  →  promote one at a time  →  merge gate LAST
```

**The trigger is: `merge gate` can pass. Not before, and not on a passing remark.**

---

# Part 3 — The build queue

| # | Work | Depends on | Where it lands |
|---|---|---|---|
| **W0** | Application Layer documents + `Human Instruction` killed | — | PR #18 |
| **W1** | A1 base-branch enforcer · A2 CODEOWNERS · A4 §P correction | — | PR #19 · #20 · #21 |
| **W2** | Tally XML/HTTP: spec study, envelope models, parser, validator, interface | one sample for the live half |  |
| **W3** | Six artifact schemas · Transaction ID format · Brain interface contract | Amendment 2 |  |
| **W4** | Conformance predicates · the five safety gates · five rejection canaries · ID-ablation test | W3 |  |
| **W5** | Held-out sealing — **structural, not disciplinary** | W3 |  |
| **W6** | Strong baseline — regex + vendor→ledger lookup + GST rate table | W3 |  |
| **W7** | Document collection + provenance manifest + negative controls | D1 |  |
| **W8** | A3 — implement every placeholder gate whose infrastructure now exists | W3–W7 |  |
| **W9** | Application Layer skeleton · Brain stub · engine stubs · walking skeleton | W3 |  |

**Every pull request touching `.github/**` or the branch ruleset is opened and left
unmerged.** Those surfaces are the user's.

---

# Part 4 — What remains the user's alone

```
1  Six definitions · finish conditions · the absolute floor      sign-off
2  The human ceiling                                             never fabricated
3  WaitingForApproval — approve or reject                        blocks the architecture freeze
4  One authentic Tally XML sample                                unblocks the live half
5  One free LLM API key                                          into GitHub secrets, never into code
6  Ruleset promotions                                            one gate at a time, when each can pass
```

**Everything else is scheduled above.**

---

# Standing constraints this queue operates under

```
gate count only goes UP          a diff removing any workflow, job, step, check or
                                 assertion is a violation regardless of reason
never weaken a test              stricter only, or to correct a wrong expectation
no placeholder passes as done    stubs only where P3 schedules them, labelled as stubs
no accuracy claim before ceiling Law 52
never fabricate a number         including a threshold. Missing one → stop and ask
no secrets in code or logs       ever
external input is hostile        every downloaded document included
.github/** reported line by line before and after
the branch ruleset is never edited
```
