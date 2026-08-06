# OWNER DECISION QUEUE

> Every item here has had its engineering done to the signature line. None is an
> open question. Each is a **yes / no / pick-one**, with the work already
> finished behind it and the failure mode of each option stated.
>
> **Why this file exists.** These four were reported as *"that's yours"* and left
> there. That was wrong: the standing rule is to shrink the owner set to the
> smallest possible, and "shrink" means doing everything up to the decision, not
> stopping at the boundary and naming it. Three of the four below could have been
> drafted days earlier.

Bound to commit `55eb987`. Nothing here blocks Engine 1 — engineering continues
around every item (Decision 1, 2026-08-06).

---

## D-A · Acceptable software licences — `license scan` (PH-04)

**Status: MEASURED, one line from done.**

The gate has never run because nobody stated which licences are acceptable. That
sounded like a legal research project. It is not — the set is small, finite, and
already on disk.

**Every licence actually present across all 24 pinned distributions**, read from
installed metadata, not from memory:

| Count | Licence |
|---|---|
| 8 | MIT / MIT License |
| 6 | Apache-2.0 / Apache Software License / Apache 2.0 |
| 3 | BSD-3-Clause / BSD |
| 1 | MIT-CMU |
| 1 | `BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0` |
| 1 | `Apache-2.0 AND Apache-2.0 WITH LLVM-exception AND BSD-2-Clause` |
| 1 | `BSD-3-Clause, Apache-2.0, dependency licenses` |
| **1** | **`Dual Licensed - GNU AFFERO GPL 3.0 or Artifex Commercial License`** |

*(`paddleocr` and `paddlepaddle` are not installed in the local venv; both are
Apache-2.0 upstream and must be confirmed on a CI runner before this locks.)*

**Exactly one non-permissive entry exists, and it is PyMuPDF — the thing D-D is
about.** Everything else is MIT, Apache, BSD, Zlib or CC0.

**THE DECISION — one word.** Approve this allowlist, derived from what is
actually here rather than invented:

```
MIT · MIT-CMU · Apache-2.0 (incl. LLVM-exception) · BSD-2-Clause ·
BSD-3-Clause · 0BSD · Zlib · CC0-1.0 · MPL-2.0*
```

*MPL-2.0 appears only via `pikepdf`, a transitive of `img2pdf`, which D-D does
not need. Include it only if you want headroom.

**Anything outside the list fails the gate.** AGPL, LGPL and unlicensed are
excluded by construction — LGPL explicitly, because the F-001 work found
`img2pdf` is **LGPLv3 and not MIT** as it had been described.

**What could go wrong:** a future dependency arrives under a licence that is fine
but unlisted, and the gate blocks a legitimate change. Cost: one line added here.
That is the correct direction — a gate that fails closed on an unknown licence is
doing its job.

**Approved:** ______________________  Date: __________

---

## D-B · Does the MVP ship as a container? — `docker build` (PH-10)

**Status: BLOCKED ON YOU, and genuinely so.**

`quality.yml` states it plainly: *"the only gate with no basis in any
architecture document."* There is no Dockerfile because **no locked document
names a deployment target at all.**

**Why I did not just write one.** Law 20 — never change architecture without an
approved amendment. Choosing a deployment shape and writing the file that
enforces it *is* an architecture decision, made silently, in a repository whose
whole design is that such decisions are explicit. Writing a Dockerfile would have
made the gate green and the architecture a fiction.

**THE DECISION — pick one:**

**(a) Container.** I write the Dockerfile, `docker build` binds to "the image
builds and the CLI runs inside it", and it becomes a real gate.
*Failure mode:* ~200 MB of ML wheels per image; build time on the critical path.

**(b) Not a container — CLI only.** The gate is rewritten to enforce the
invariant that actually matters instead: the wheel installs offline into a clean
interpreter and the CLI entry point runs. That is a real property, testable
today, and the gate stops being decorative.
*Failure mode:* no deployment story until someone needs one.

**(c) Defer explicitly.** Stays red with a documented reason.
*Failure mode:* your "every Action green" definition stays unreachable.

**My recommendation: (b).** The blueprint already says CLI, no UI. A container
gate on a product that ships as a CLI enforces nothing about the product. Under
your F-008 rule the correct move for a gate enforcing nothing is to **bind it to
a real invariant**, not to remove it — and (b) is exactly that.

**Decision:** ______________________  Date: __________

---

## D-C · `end-to-end` drives a browser that does not exist — (PH-13)

**Status: BLOCKED ON YOU. The only placeholder no phase can clear.**

Its milestone is literally `NEVER-IN-MVP`. It runs Playwright.
`MVP_IMPLEMENTATION_BLUEPRINT.md:41` says **"CLI, no UI."** There is nothing to
drive, and no amount of building will create something — the blueprint forbids
the thing the gate tests.

**THE DECISION — pick one:**

**(a) Re-point it at the CLI.** An end-to-end run becomes: a real document enters
`pipeline.run` and a Document Evidence Object comes out, asserted end to end. §M
amendment to `MVP_IMPLEMENTATION_BLUEPRINT.md` replacing the browser assumption.
*Failure mode:* overlaps `integration tests`; the two must be given distinct
invariants or one becomes noise.

**(b) Amend the blueprint to include a UI.** Scope change.
*Failure mode:* large, and nothing currently asks for it.

**(c) Defer explicitly.** Documented as unreachable in the MVP.
*Failure mode:* same as D-B(c).

**My recommendation: (a).** It converts a gate that can never pass into one that
tests the only thing Engine 1 promises — a truthful DEO from a real document.
Same F-008 logic as D-B: bind it, do not remove it.

**Decision:** ______________________  Date: __________

---

## D-D · Replace PyMuPDF with pypdfium2 — F-001

**Status: FULLY MEASURED. Amendment drafted at
`AMENDMENT_DRAFT_F001_PDF_BACKEND.md`, signature line unsigned.**

The one item that was already done properly. Full benchmark across 16 documents /
219 pages / six producer toolchains.

**The finding that decided it:** pdfminer.six and pdfplumber **fabricate digits**
— `(cid:28)` rendered as 2,660 ASCII digits corresponding to no glyph on the
page, 9.28% of every digit they emit, indistinguishable from printed text and
rejectable by no filter. Disqualified on the non-goal, not on performance.

pypdfium2 covers all eight operations alone, is BSD/Apache, is **already pinned**
at `requirements-engine1.txt:104`, and is faster (10.94 vs 15.57 ms/page) and
smaller (7.5 vs 55.4 MB).

**What would prove this wrong, stated in advance:** the corpus contains **zero
real GST invoices.** pypdfium2 emits U+FFFE for hyphens in subset fonts lacking
`ToUnicode` — zero occurrences on all four invoice fixtures, but if Indian GST
software emits such fonts it corrupts invoice numbers and GSTINs. It is
survivable only because U+FFFE is a noncharacter and therefore **detectable**,
where `(cid:28)` is not. **Cheap test that settles it: ten real GST invoices,
count noncharacters.**

**Decision:** ______________________  Date: __________

---

## Not on this queue, and why

**F-006 golden dataset (16 vs ~100 documents)** and **T-005 the sixteen unset
confidence parameters** are owner items, but neither blocks Engine 1 under the
permanent bottleneck rule: Engine 1 turns artifacts into a truthful DEO and never
reasons about accounting. Decision A7 also removed the threshold gating those
sixteen numbers were for. They belong to the Brain and to P4.

---

# Engine 2 — added 2026-08-06

Engine 2 design is authorized and under way. Implementation is not. These are what
stand between the finished design and the first line of Engine 2 code.

---

## D-E · Gemini 2.5 Flash — an API key, and permission to spend

**Status: HARD BLOCKER. Nothing engineering can do reduces it.**

`docs/TECHNOLOGY_STACK.md` locks Gemini 2.5 Flash as Engine 2's reasoning model.
**Six of the engine's seven sub-engines are that model and nothing else** —
Transaction, Party, Item, Payment, Timeline, Business Context.

**Why there is no way around it.** A hardcoded or faked model would make the seam
look alive while every downstream number measured invention. `ENGINE_2:878` names
that as this engine's own failure: *"a fact is invented to complete the story."*
Building the six behind a fake is worse than not building them.

**What is NOT blocked by it, and is proceeding now:** the entire design —
architecture, Story Builder's specification, contracts, the confidence model,
evaluation methodology, synthetic datasets, adversarial cases, the implementation
plan and package layout.

**THE DECISION:** provide a key and state a spend ceiling, or say "not yet" and the
six sub-engines stay frozen while everything around them is finished.

**Cost is UNMEASURED.** Calls per document follow from the seven-sub-engine design;
a figure will be estimated in `ENGINE_2_IMPLEMENTATION_PLAN.md` and labelled an
estimate until a real run measures it.

**Decision:** ______________________  Date: __________

---

## D-F · Amendment 4 — release Engine 2 implementation

**Status: DRAFTED, unsigned. `CLAUDE.md` §P.**

Currently marked **DRAFT — NOT SIGNED, NOT IN FORCE**, and `ENGINE_2_AUTHORIZED` in
`tests/unit/test_package.py` is deliberately **empty**. Three guards already exist
and have been proven against that empty set, so the day it is signed, one line
changes and the guards are already known to work.

**Two shapes to choose between:**

**(a) Story Builder only.** The one sub-engine specified as pure assembly —
*combine · organize · create*. Needs no model, no key, no spend. Buildable the hour
it is signed. *Failure mode:* Engine 2 has an assembly layer with nothing to
assemble until D-E is answered.

**(b) All seven.** Requires D-E first, since six of them are the model.

**Recommendation: (a) now, (b) when D-E is answered.** It converts the one part of
Engine 2 that is genuinely unblocked into working code, and it does it under a
narrower amendment that cannot be mistaken for a general release.

**Decision:** ______________________  Date: __________

---

## D-G · The two posting thresholds

**Status: named, deliberately UNSET, and blocking nothing today.**

The §M amendment's posting policy requires:

```text
1. Understanding Confidence >= approved posting threshold
2. Evidence Reliability     >= approved reliability threshold
```

**Both are owner values and no number is chosen** (Law 10, Law 52). Until they are
set, conditions 1 and 2 cannot be satisfied and **nothing auto-posts**. That is the
correct failure direction and is not an oversight.

**Do not answer this yet.** The amendment also requires calibration against labelled
accounting data before any raw confidence may be read as a probability. Setting a
threshold before that calibration would be choosing a number on no evidence — the
exact failure Law 52 exists to prevent. It is listed here so it is not forgotten,
with its precondition attached.

**Blocked on:** labelled accounting data (P1 / the golden set).

**Decision:** ______________________  Date: __________
