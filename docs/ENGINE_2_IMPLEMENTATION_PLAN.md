# Engine 2 — Understanding Engine: Implementation Blueprint

> **Precedence level 5 — a plan, not a lock.** Subordinate to
> [`SYSTEM_INVARIANTS.md`](SYSTEM_INVARIANTS.md),
> [`ENGINE_2_UNDERSTANDING_ENGINE_RULES.md`](ENGINE_2_UNDERSTANDING_ENGINE_RULES.md)
> and the two Understanding communication contracts. **Where this document
> contradicts any of them, this document is wrong** (CLAUDE.md §H: *"If they
> conflict, architecture wins."*)
>
> **Status: DESIGN ONLY. Nothing here is built.** `CLAUDE.md` §P Amendment 4 is
> an **unsigned DRAFT** and releases nothing. This is the §H blueprint written
> so that implementation can begin the hour it is signed — the reason the
> amendment's own preamble gives: *"when this is signed, implementation starts
> the same hour because the design is already finished."*
>
> **Base commit: `d7a8ed9`.** Every path, line number and quotation below was
> read off the tree at that commit, never recalled.

---

## 0. Read this first — the state of the amendment at `d7a8ed9`

**Amendment 4 does not exist in this worktree.** Neither does `ENGINE_2_AUTHORIZED`.

```
grep 'Amendment 4' CLAUDE.md                         -> 0 matches
grep -r 'ENGINE_2_AUTHORIZED' tests/ src/ docs/      -> 0 matches
```

Amendment 4 exists only in the shared checkout's working copy of `CLAUDE.md`,
which carries it as an explicitly unsigned draft. `d7a8ed9` predates it. So the
freeze in force **on this branch** is Amendment 3's: *"Engine 1, and only Engine
1, is released… Nothing outside Engine 1 is authorized by this amendment."*

Three consequences, stated up front so no step below is read as permission:

1. **Not one file under `src/` may be created or modified** to execute this plan.
   `tests/unit/test_package.py::test_the_other_five_engines_remain_frozen`
   refuses every module under `engines/understanding_engine/` that is not
   `__init__` or `stub`, and it is correct to.
2. **Amendment 4 as drafted is narrower than this plan's full target.** It
   releases *"Story Builder (§8.7), the sub-engine orchestration order (§7), and
   their interfaces, tests and documentation"* — **two** components — and keeps
   *"the six reasoning sub-engines… FROZEN, as do all LLM/AI calls anywhere in
   the engine."* §1 below therefore gives the authorized set **twice**: the
   two-module set a signed Amendment 4 permits, and the eleven-module target the
   engine reaches when the model is released by a later amendment. They are
   different lists and this document never conflates them.
3. **This file is the only artifact this work produces.** No source, no tests, no
   requirements manifest, no CI change.

---

## H1. Goal

**Convert the Document Evidence Objects sharing one Transaction ID into one
Business Understanding Object whose story carries enough for an accountant to
reach the same treatment they reached from the documents themselves.**

### The measurable finish line (Law 52)

Copied from `MVP_IMPLEMENTATION_BLUEPRINT.md:25`, condition 7 of nine, and from
`ACCOUNTING_DEFINITIONS.md` §2, which is the definition that makes it measurable:

```
understanding correctness  >=  80% of the FROZEN human ceiling
```

Measured exactly as `ACCOUNTING_DEFINITIONS.md` §2 specifies and no other way:

| Step | |
|---|---|
| 1 | A qualified accountant produces a treatment **from the documents** — recorded |
| 2 | **A separate sitting, minimum one week later** |
| 3 | The same accountant produces a treatment **from the Transaction Story alone**, never seeing the document |
| 4 | Compare. Same treatment = understanding was correct. Different = the story lost something load-bearing |

**This number cannot be produced today, and no proxy for it may be reported.**
It needs the frozen ceiling, which is P1's and does not exist
(`CLAUDE.md` §P: *"Ground truth — 25 documents, 2 accountants, frozen ceiling —
❌ None exists"*). Until it does, every Engine 2 accuracy claim is **UNMEASURED**,
and Law 52 forbids stating one.

### The three numbers that CAN be produced before P1, and are therefore this plan's gates

These are engineering floors, not accuracy claims. They are the existing
repository gates applied to new code, and they are what "done" means for every
phase below:

| Gate | Threshold | Source |
|---|---|---|
| `unit tests` | 100% passing | `testing.yml` |
| `coverage` | the **higher** of 93% and the base branch's actual | `testing.yml`, *"coverage floor is the HIGHER of 93 and the base branch's actual"* |
| `mutation` | **≥ 93%** | `testing.yml`, *"mutation score at or above 93 percent"* |

`pyproject.toml` `[tool.mutmut] do_not_mutate` excludes `*/engines/*/stub.py`.
It does **not** exclude anything else under `engines/`. **Every module this plan
creates is mutated from its first commit** — there is no grace period, and none
is requested.

### What this build is for, in one line

`ACCOUNTING_DEFINITIONS.md` §2 states the stake plainly, and it is the reason
Engine 2 is worth building carefully rather than quickly:

> *"It is also the only metric that tests the architecture's central bet — that
> a business story can carry an accounting decision without the document. **If
> that bet is wrong, the six-engine split is wrong**, and nothing else in the
> measurement suite would tell you."*

---

## H2. Non-Goals

Copied from `ENGINE_2_UNDERSTANDING_ENGINE_RULES.md` §6 and §3, then extended
with what planning surfaced.

### From the locked specification — absolute

**Referenced, deliberately not restated.** `ENGINE_2:266-274` states the seven
absolute prohibitions — the seventh, *"convert uncertainty into certainty"*,
being the one `:278` calls the rule this engine exists to protect. `ENGINE_2:81-85`
states what the engine does not own: accounting treatment · ledger or account
selection · tax determination · journal entries · any decision about how the
transaction is recorded.

> **Why this section points instead of copying**, and it is not a style choice.
> `ENGINE_2:153` sets the convention — *"This document references it; it does not
> restate it."* A prohibition copied into a second document is a second source of
> truth that can drift (Law 19), and `tests/unit/test_conformance_registry.py`
> enforces it mechanically: it scans every file in `docs/` for the prohibition
> marker and **fails** on any clause not carried by a rule in the registry.
> Restating those seven here would have created seven clauses this plan has no
> authority to state. Verified by reproducing the scanner's own logic against
> this file.

### Discovered while planning — additions this document makes explicit

| # | Not a goal | Why it is named here |
|---|---|---|
| N-1 | **Making the six reasoning sub-engines "work" behind a fake model** | Amendment 4's own words: *"Building them behind a fake model would make the seam look alive while measuring invention, which `ENGINE_2:878` names as the engine's own failure mode."* A recorded-transcript replay backend (§2.4) is **not** a fake model — it replays a real model's real answers — and the distinction is load-bearing |
| N-2 | **Any accuracy number before P1's ceiling is frozen** | Law 52 · `CLAUDE.md` §P: *"no accuracy claim before the ceiling exists"* |
| N-3 | **Choosing temperature, seed, top-p, max tokens, timeout, retry count, or a spend cap** | Law 52 and the `render_dpi` precedent: *"no document in this repository states a render DPI, and choosing one would answer a question put to the owner"* (`pdf_backend.render_page_png`). Every one of these is an owner number. §5 lists them |
| N-4 | **Building the OpenRouter fallback** | It has **no trigger**, exactly as Engine 1's Gemini Vision fallback has none, and `ARCHITECTURE_AMENDMENTS.md` Amendment 8 forbids a confidence threshold from becoming one. See C-8 |
| N-5 | **An `assembly.py` for Engine 2** | Engine 1 has one because `ENGINE_1_INPUT_ENGINE_RULES.md:384` says *"No new assembler sub-engine is created"* and the parent must assemble. Engine 2 is the **opposite**: assembly IS a sub-engine here (`story_builder`, §8.7). An Engine 2 `assembly.py` would be an eighth sub-engine (see C-4) |
| N-6 | **Adding spaCy work** | `TECHNOLOGY_STACK.md` §Engine 2 lists spaCy for *"linguistic processing"* and **no locked document says what it is for**. It is unblocked by the API key and still unauthorized. Recorded, not planned (see C-10) |
| N-7 | **Resolving any of the six `SPEC_GAPS`** already recorded in `src/accountant_dad/artifacts/understanding.py` | They are owner or document questions. The code records them; this plan does not settle them |
| N-8 | **Consulting the Brain** | `ENGINE_2_UNDERSTANDING_ENGINE_RULES.md`, `COMMUNICATION_RULES_UNDERSTANDING_ENGINE.md` and `COMMUNICATION_RULES_UNDERSTANDING_INTERNAL.md` mention the Brain **zero times** (measured). `BLUEPRINT:99` lists Engine stubs 2–6 as its consumers. `stub.py` already records the disagreement and declines. This plan declines identically |

---

## H3. Dependencies — both directions

### What Engine 2 needs

| Needs | Phase | State at `d7a8ed9` | Verified how |
|---|---|---|---|
| `artifacts/understanding.py` — the seven Result types, `TransactionStory`, `ConfidenceAssessment`, `BusinessUnderstandingObject` | P2 | ✅ **Complete, 600 lines, already enforces the engine's four hardest invariants** | Read in full |
| `artifacts/evidence.py` — `DocumentEvidenceObject`, the input artifact | P2 | ✅ Complete | Imported by `stub.py` |
| `identity.py` — `IdentityEnvelope`, `ArtifactId`, `TransactionId`, `FIRST_VERSION` | P2 | ✅ Complete | Imported by `stub.py` |
| `confidence.py` — the one `Confidence` representation | P2 | ✅ Complete | Imported by `artifacts/understanding.py` |
| `services/pipeline.py` — the Application Layer runner and the Engine 2 call site | P3 | ✅ Complete; calls `StubUnderstandingEngine().understand(...)` at line 394 | Read |
| Engine 1 producing a real Document Evidence Object | P4 | ✅ `engines/input_engine/pipeline.py` exists and runs | Read |
| **A Gemini API key and authorized spend** | P4 | ❌ **Does not exist** | `TECHNOLOGY_STACK.md:135`, blocker table |
| **P1's frozen human ceiling** | P1 | ❌ **Does not exist** | `CLAUDE.md` §P |
| **A named artifact carrying "the business's own operating history"** | — | ❌ **Does not exist anywhere** | See C-7 — the single largest hole |
| **A signed Amendment 4** | — | ❌ Draft, unsigned | §0 |

**The reuse finding, stated because Law 15 requires checking before proposing:**
`artifacts/understanding.py` is **not a skeleton — it is finished, and it is
strict.** It already enforces, structurally:

- a fact cannot exist without an evidence reference (`ObservedFact._a_fact_names_its_evidence`)
- a Result's evidence references are **derived** from its facts, never stored, so a
  Result cannot declare evidence its facts do not cite nor omit evidence they do
- `missing_information` and `detected_conflicts` are **derived**, so dropping one
  from the artifact "is not a thing that can be expressed"
- `identified_unknowns` must be a **superset** of every unknown the six Results
  raised (`_nothing_the_results_raised_was_lost`)
- understanding confidence ≤ evidence confidence, per Result **and** in aggregate
- understanding confidence ≤ the **lowest** Result confidence (a deliberately
  strict reading of `:638` + INV-2, recorded as such)
- authored text is vocabulary-checked against `FORBIDDEN_VOCABULARY`; quoted
  document text (`StatedText`) is never checked and never trimmed
- a `Conflict` needs ≥ 2 **distinct** competing readings and has no field for a
  resolution

**Nothing in §1 rebuilds any of that.** Every sub-engine below returns one of
these existing types. The plan's job is to produce them, not to redefine them.

### What needs Engine 2

| Consumer | Contract |
|---|---|
| **Engine 3, Accounting Engine** — the sole recipient | `COMMUNICATION_RULES_UNDERSTANDING_ENGINE.md` §1: *"its sole recipient is the Accounting Engine. It does not communicate with the Clarification, Validation or Execution Engines, and it does not communicate with the user"* |
| **Engine 4, Clarification** — indirectly | `ENGINE_2` §12. Engine 2 detects and names gaps; it may never ask a question. Every `Unknown.why_it_matters` exists so Engine 4 can turn it into a good question |
| **Engine 5, Validation** — returns work | `COMMUNICATION_RULES_UNDERSTANDING_ENGINE.md` item 9: a finding that a **business fact** is wrong returns to Understanding; one a human could resolve returns to Clarification |
| `services/pipeline.py` | Holds the one call site. This is what makes every rollback in H9 a one-line revert |

---

## H4. Acceptance Criteria — judged by a non-engineer

Each is a sentence the owner can read and judge, and each carries a number.

| # | Criterion | Number |
|---|---|---|
| **A-1** | An accountant handed only the Transaction Story reaches the same treatment they reached from the documents, a week apart | **≥ 80% of the frozen ceiling** (`BLUEPRINT:25`) |
| **A-2** | When two documents disagree, the story **says they disagree** and names both readings — it never picks one | **100% of injected conflicts survive to `detected_conflicts`.** One silently resolved conflict fails the build |
| **A-3** | Everything the story asserts can be pointed at on a document | **100% of facts carry ≥ 1 evidence reference, and every reference resolves to a real reference in the input batch.** Already half-enforced by `ObservedFact`; the closed-world half is §2.3 |
| **A-4** | Nothing the sub-engines flagged as unknown goes missing from the final artifact | **0 dropped unknowns.** Already structurally enforced by `_nothing_the_results_raised_was_lost` |
| **A-5** | The system never sounds more sure than the reading it was given | **0 violations** of understanding ≤ evidence, and of understanding ≤ min(Result). Already structurally enforced |
| **A-6** | No accounting word appears in anything the engine wrote itself | **0 hits** of `FORBIDDEN_VOCABULARY` in authored text. Already enforced at runtime; §2.5 adds the identifier-level guard |
| **A-7** | Running the same documents twice produces the same story | **byte-identical artifacts across 3 runs**, model calls replayed from transcript. This is what makes A-1 measurable at all — `BLUEPRINT:184`: *"High spread across repeats… Unpredictable disqualifies it regardless of average"* |
| **A-8** | The engine costs a knowable amount per document | **6 model calls per transaction, exactly** — derived in §7, architecturally pinned. Token volume and price: **UNMEASURED** |

**A-2 through A-7 are gradeable before P1 exists.** Only A-1 and A-8's price half
wait on the owner. That asymmetry is the reason for the build order in H5.

---

## H5. The Plan

### 1. Package layout — the exact module paths

#### 1a. What a signed Amendment 4 authorizes, verbatim

Amendment 4 as drafted releases the deterministic layer only. `ENGINE_2_AUTHORIZED`
would therefore be exactly this, and nothing else:

```python
#: CLAUDE.md §P, Amendment 4 — Engine 2, DETERMINISTIC LAYER ONLY.
#: *"Story Builder (§8.7), the sub-engine orchestration order (§7), and their
#: interfaces, tests and documentation."* The six reasoning sub-engines and all
#: LLM/AI calls remain FROZEN.
#:
#: Exhaustive, like ENGINE_1_AUTHORIZED and for the same reason: an exhaustive
#: list makes an eighth sub-engine VISIBLE, where a pattern such as "anything
#: under understanding_engine" would admit code nobody reviewed.
ENGINE_2_AUTHORIZED = {
    "engines/understanding_engine/story_builder",  # §8.7 — assembly; publishes the artifact
    "engines/understanding_engine/pipeline",       # the ENGINE's own runner: §7's order
}
```

#### 1b. The full target, when the model is released

The remaining six arrive with the amendment that releases the model. Names are
**not chosen here** — they are `SUB_ENGINE_RESPONSIBILITIES.md` §2.1–2.7's own
snake_case identifiers, quoted, not paraphrased:

```
engines/understanding_engine/transaction_understanding   §2.1 -> Transaction Understanding Result
engines/understanding_engine/party_understanding         §2.2 -> Party Understanding Result
engines/understanding_engine/item_understanding          §2.3 -> Item Understanding Result
engines/understanding_engine/payment_understanding       §2.4 -> Payment Understanding Result
engines/understanding_engine/timeline_understanding      §2.5 -> Timeline Understanding Result
engines/understanding_engine/business_context            §2.6 -> Business Context Result
engines/understanding_engine/story_builder               §2.7 -> Business Understanding Object
engines/understanding_engine/pipeline                    parent machinery — not a sub-engine
engines/understanding_engine/__init__                    plumbing  (already on AUTHORIZED_STUBS)
engines/understanding_engine/stub                        the P3 stub (already on AUTHORIZED_STUBS)
```

**Ten paths. Seven sub-engines, one runner, two already-authorized.**

#### 1c. Where the model seam does NOT go

```
src/accountant_dad/model_backend.py        <- OUTSIDE engines/understanding_engine/
```

**This is not a preference. It is `pdf_backend.py`'s stated reason, applied.**
`test_package.py:62-76` records why `pdf_backend` sits at the package root and
not under `engines/input_engine/`:

> *"'Engine 1 never depends directly on PyMuPDF' is only true if the file that
> does is outside Engine 1; a PyMuPDF import under `engines/input_engine/` is the
> dependency the ruling removes, wherever in that directory it sits."*

Identically: *"Engine 2 never depends directly on Gemini"* is only true if the
file that does is outside Engine 2. And it buys something Engine 1's version
could not — because `AI_VENDOR_PACKAGES` (`test_package.py:405`) already contains
`"google"`, a test asserting **Engine 2 imports zero AI vendor packages** can be
written on day one and **never relaxed**, at any phase, forever. Put the client
inside the engine and that guard has to be punctured the day the model arrives.

`model_backend` is preferred over `reasoning_backend` because "reasoning" is the
word `TECHNOLOGY_STACK.md` uses for what Engine 3 may **never** do, and a file
named for it invites the wrong reading. Neither name hits `FROZEN_MARKERS`
(`"engine"·"accounting"·"tax"·"llm"·"openai"·"anthropic"·"tally"·"brain"`) — checked.

**`model_backend.py` is not authorized by Amendment 4 as drafted.** Amendment 4
freezes *"all LLM/AI calls anywhere in the engine"*, and a module whose purpose is
to make one is that. It is **designed** in §2 and **written** when the model is
released.

#### 1d. The three-category classification, stated BEFORE the code

Engine 1 shipped nine modules against a locked *"exactly four sub-engines"* and
nobody could say whether the code violated the lock. That cost a day and needed
`ARCHITECTURE_AMENDMENTS.md` **Amendment 5** to state the membership test
(`KNOWN_FAILURES.md` F-010). **Engine 2 walks into the identical trap** — *"exactly
seven"* (`ENGINE_2:292`), ten modules — so the predicate goes in first this time.

The locked documents already supply it.
`COMMUNICATION_RULES_UNDERSTANDING_INTERNAL.md` Rule 1: *"Each sub-engine
publishes exactly one named **Result**, and that Result is the entirety of what
siblings may see."* Therefore:

> **A component is an Engine 2 sub-engine IF AND ONLY IF it publishes one of the
> seven named Results.**

That predicate is checkable and sorts all ten without a judgement call:

| Category | Modules | Count |
|---|---|---|
| **SUB-ENGINE** — publishes a named Result | the seven above | **7, pinned. An eighth is FORBIDDEN** |
| **PARENT MACHINERY** — the engine's own runner | `pipeline` | 1 |
| **NOT A COMPONENT** — plumbing and the P3 stub | `__init__`, `stub` | 2 |
| **FACILITY** — produces no part of any Result | *(none)* | 0 |

**Note the inversion from Engine 1, and it is the whole reason `assembly.py` must
not exist here.** For Engine 1, assembly is parent machinery, because
`ENGINE_1_INPUT_ENGINE_RULES.md:384` says *"No new assembler sub-engine is
created."* For Engine 2, assembly **is** a sub-engine — `story_builder`, §8.7,
which publishes the Business Understanding Object. An Engine 2 module that
combined Results without being `story_builder` would publish part of the artifact
and be an eighth sub-engine in all but name.

**The falsifier for the "no facility" claim**, stated in advance the way
Amendment 5 states its own: *a module under `engines/understanding_engine/` that
neither publishes a Result nor calls the seven in order.* If one appears, this
table is wrong and the module must be classified before it is merged, not after.

---

### 2. Interfaces

#### 2.1 The six reasoning sub-engines — one shape, six instances

Every one has the same signature shape, and the differences are exactly the ones
§8 specifies. `transaction_understanding` is the only one that does not receive a
Result; the four enrichers receive the Transaction Result; `business_context`
receives five.

```python
# transaction_understanding.py                     ENGINE_2 §8.1 · SUB_ENGINE §2.1
def understand_transaction(
    evidence: tuple[DocumentEvidenceObject, ...],
    *,
    model: ModelBackend,
) -> TransactionUnderstandingResult: ...

# party_understanding.py                           ENGINE_2 §8.2 · SUB_ENGINE §2.2
def understand_parties(
    evidence: tuple[DocumentEvidenceObject, ...],
    transaction: TransactionUnderstandingResult,
    *,
    model: ModelBackend,
) -> PartyUnderstandingResult: ...

# item_understanding.py       -> ItemUnderstandingResult       (same shape as party)
# payment_understanding.py    -> PaymentUnderstandingResult    (same shape as party)
# timeline_understanding.py   -> TimelineUnderstandingResult   (same shape as party)

# business_context.py                              ENGINE_2 §8.6 · SUB_ENGINE §2.6
def understand_context(
    evidence: tuple[DocumentEvidenceObject, ...],
    transaction: TransactionUnderstandingResult,
    party: PartyUnderstandingResult,
    item: ItemUnderstandingResult,
    payment: PaymentUnderstandingResult,
    timeline: TimelineUnderstandingResult,
    *,
    model: ModelBackend,
    operating_history: OperatingHistory,   # <- C-7: NO SUCH ARTIFACT EXISTS
) -> BusinessContextResult: ...
```

Four properties of these signatures are deliberate and each is falsifiable:

1. **`evidence` is a tuple, never one document.** `ENGINE_2:157` — the engine
   receives *all* Document Evidence Objects sharing one Transaction ID.
   *"Extraction is document-centric. Understanding is transaction-centric."* A
   signature taking one document would make the cross-document conflict of `:165`
   unexpressible.
2. **Siblings are passed as whole Results, never as extracted fields.**
   `UNDERSTANDING_INTERNAL` Rule 1: the Result *"is the entirety of what siblings
   may see."* Passing `transaction.identified_event` instead of `transaction`
   would be a side channel by decomposition.
3. **`model` is injected, never constructed inside.** This is what lets every one
   of the six be tested against a recorded transcript with zero spend, and it is
   the same discipline `detected_fields` states for the clock: *"a module calling
   `uuid4()` or `datetime.now()` cannot offer [reproducibility]."*
4. **Every return type already exists** in `artifacts/understanding.py`. Nothing
   here defines a new one.

`business_context`'s `operating_history` parameter is written with its defect
attached rather than quietly omitted — see C-7. **It is the reason
`business_context` is last in the build order and cannot be built by closing the
API-key blocker alone.**

#### 2.2 `story_builder` — the one that needs no model

```python
# story_builder.py                                 ENGINE_2 §8.7 · SUB_ENGINE §2.7
def build_story(
    results: SupportingUnderstandingData,
    evidence_confidence: Confidence,
    *,
    artifact_id: ArtifactId,
    transaction_id: TransactionId,
) -> BusinessUnderstandingObject: ...
```

**No `model` parameter, and that absence is the design.** §8.7's entire allowed
list is *combine · organize · create*, and its forbidden list is precisely the set
of things a model would do: *resolve conflicts · choose the "correct"
interpretation · remove unknowns · increase confidence · add a fact no sub-engine
produced.* A `story_builder` that could reach a model could do all five. **A
signature with no way to reach one cannot.**

`evidence_confidence` is a parameter rather than something `story_builder`
computes, and this is the one place the plan flags an unresolved decision rather
than making it. §8.7 says it receives *"the Confidence Report within the Document
Evidence Object"* — but a batch holds many documents and each holds many field
scores, so *"the"* evidence confidence needs an aggregation rule **no document
defines.** `stub.py` already names this and refuses to invent one:

> *"'the' evidence confidence would need an aggregation rule that no document
> defines — choosing one is Law 54's undefined term settled silently by the
> engineer."*

Passing it in moves the decision to a caller who must be told to make it, instead
of hiding it inside the assembler. **It is an owner item** (§5, O-7).

#### 2.3 `model_backend.py` — the ONE boundary through which a model is reached

Read `src/accountant_dad/pdf_backend.py` before implementing this. Its core
sentence is the specification for this file:

> *"**THE INTERFACE IS OPERATIONS, NOT OBJECTS, AND THAT IS THE WHOLE DESIGN.**
> Handing callers a live `pymupdf.Document` and calling that an abstraction would
> move the import and change nothing: every caller would still speak PyMuPDF's
> method names, its `get_text("dict")` dictionary shape and its
> `get_pixmap(dpi=...)` keyword."*

**The equivalent failure here is worse, because a model client is a bigger
surface than a PDF handle.** Hand a sub-engine a `genai.Client` or a Pydantic-AI
`Agent` and it will speak `generate_content`, `GenerateContentConfig`,
`response_schema=`, safety-block finish reasons and
`google.api_core.exceptions.ResourceExhausted`. Swapping to OpenRouter — the
locked fallback — would then mean editing six sub-engines. **`pdf_backend` hands
out no backend object for exactly this reason, and neither does this.**

```python
class ModelBackend(Protocol):
    """The one way Engine 2 reaches a language model.

    Deliberately a single method. No client, no session, no agent and no
    response object crosses this boundary: a caller holding one of those is
    speaking the vendor's language, which is the thing this file exists to
    prevent.
    """

    def interpret[T: BaseModel](self, request: Interpretation[T]) -> T: ...


@dataclass(frozen=True, slots=True)
class Interpretation[T: BaseModel]:
    #: The sub-engine's own words. Authored by Engine 2, never by this module.
    instruction: str
    #: Evidence, verbatim off the Document Evidence Object. Never paraphrased
    #: here -- ENGINE_2:190 makes it read-only to this engine, permanently.
    evidence: str
    #: The shape the answer must take. One of the six Result component models,
    #: owned by the sub-engine. This module never defines an output shape.
    answer: type[T]
    #: CLOSED WORLD. Every evidence reference the answer may cite. A response
    #: citing anything outside this set is REFUSED, never trimmed to fit.
    citable: frozenset[str]
    #: What makes two runs the same run. See `transcript` below.
    request_key: str
```

**Five prohibitions, each with the line that forces it:**

| # | The boundary refuses | Because |
|---|---|---|
| B-1 | Handing out any vendor object — client, agent, session, response, usage record | `pdf_backend`'s stated design. `PdfDocument` is a Protocol with `close()` and **nothing else**; here nothing at all crosses |
| B-2 | Letting a vendor exception escape | `pdf_backend` converts exactly one (`FileDataError` → `BrokenPdfError`) *"so the taxonomy belongs to Engine 1 and the backend keeps its exceptions to itself."* Same here: one named `ModelRefusedError` for a model that would not answer, carrying the vendor message **verbatim** and the original as `__cause__` — *"naming a failure must not cost the diagnosis"* |
| B-3 | Returning free text | A sub-engine that parses vendor-shaped prose has the vendor's shape in it. The answer is an instance of `T` or it is a refusal. This is where `TECHNOLOGY_STACK.md`'s **Pydantic AI · JSON Schema · Guardrails AI** live — all three behind this one file |
| B-4 | **Any answer citing an evidence reference outside `citable`** | `UNDERSTANDING_INTERNAL:130` — *"A fact with no evidence reference cannot appear in a Result. There is no mechanism for producing one, and that is deliberate: **it is the structural reason this engine cannot hallucinate**."* `ObservedFact` already refuses **zero** references. It cannot refuse a **fabricated** one, because it has never seen the batch. This check closes that half, and it is the single highest-value line in the file |
| B-5 | A default for temperature, seed, top-p, max tokens, timeout or retries | `pdf_backend.render_page_png`: *"`dpi` is required and has no default… no document in this repository states a render DPI, and choosing one would answer a question put to the owner (Law 52)."* Identical. Omitting one must fail to typecheck, exactly as omitting `render_dpi` does |

**B-4 is a check on untrusted external input, not accounting reasoning.** Law 23:
external input is untrusted, and a model response is external input. Putting it at
the seam rather than in six sub-engines is Law 14 (never duplicate logic) and §I.12
(*"if the root is a whole CLASS, fix the class"*). It is also why the seam is a
function and not an object: an object hands the caller a way to skip the check.

#### 2.4 The transcript — how a nondeterministic model is tested deterministically

**Problem transformation (Law 53), and the most valuable thing in this plan.**

The hard problem: *test a nondeterministic, metered, network-dependent model
inside a CI gate that must be reproducible, offline, free and green on every
commit.* Attacked directly, it is unsolvable — `build` installs into a **clean
offline environment**, and A-7 demands byte-identical artifacts across three runs.

The equivalent easier problem: **a recorded transcript makes every sub-engine a
pure function again.**

```
record   one budgeted, owner-authorized run  ->  request_key -> answer, on disk
replay   CI, and every developer, forever    ->  a pure dict lookup, 0 calls, 0 spend
```

Two backends implement one Protocol:

```python
class RecordingBackend:   """Calls the real model. Writes every request/answer pair."""
class ReplayBackend:      """Reads the transcript. Refuses -- never calls -- on a miss."""
```

`ReplayBackend` **must raise on a cache miss, never fall through to the network.**
A backend that silently called out would make a CI job spend money and go
nondeterministic without anyone noticing, which is `_payload_of`'s stated rule in
Engine 1's pipeline: *"a silent fallback would restore the two-pipeline
architecture while every test still passed (Law 11, §J.(a))."*

**What this buys, concretely:**

| | |
|---|---|
| CI cost of the six reasoning sub-engines | **0 calls, 0 spend, on every commit** |
| Reproducibility (A-7) | byte-identical by construction, not by care |
| Mutation testing on Engine 2 | possible at all — 93% needs thousands of runs |
| The model's own quality | measured on a **separate, scheduled, budgeted** job, not on the merge path |

This separation is the same one `ocr tests` already uses in `testing.yml` — *"the
OCR path runs, in its own interpreter"* — so it is an established pattern in this
repository, not a new one.

#### 2.5 `pipeline.py` — the runner

```python
def understand(
    evidence: tuple[DocumentEvidenceObject, ...],
    *,
    artifact_id: ArtifactId,
    model: ModelBackend,
    evidence_confidence: Confidence,
    operating_history: OperatingHistory,
) -> BusinessUnderstandingObject: ...
```

Modelled on `engines/input_engine/pipeline.py`, and held to the same three rules
that module states about itself:

- **Internal orchestration only.** *"It never calls another engine, never decides
  accounting treatment, and never routes a workflow — that is the Application
  Layer's."* Running one engine's own seven stages is not that.
- **Transforms nothing.** Every Result is handed to `story_builder` exactly as its
  author produced it (`ENGINE_2:117` — *"Each Result stands as its author produced
  it"*).
- **Never fabricates, never continues on partial reasoning.** Each stage in its
  own `try`/`except`; the first failure stops the engine, names the stage, and
  preserves every earlier Result unmodified — the `PipelineStageError` /
  `PipelinePartialResult` shape Engine 1 already uses. **No stage is ever
  substituted with an empty Result to keep the run alive**; `SupportingUnderstandingData`
  requires all six *"because a missing Result is a sub-engine that did not run,
  and `:645` requires that be reported rather than absorbed."*

---

### 3. Dependency graph and orchestration

`ENGINE_2:315-330` and `UNDERSTANDING_INTERNAL:28-43` draw the same graph twice,
identically:

```
                    tuple[DocumentEvidenceObject, ...]   (all sharing one Transaction ID)
                                    |
                    transaction_understanding            <- STRICTLY FIRST
                                    |
        +---------------+-----------+-----------+
        |               |           |           |
      party           item       payment     timeline    <- MAY RUN CONCURRENTLY
        |               |           |           |
        +---------------+-----------+-----------+
                                    |
                        business_context                 <- needs all five
                                    |
                          story_builder                  <- needs all six
                                    |
                      BusinessUnderstandingObject
```

#### What may run concurrently, and what may not

| Stage | Concurrency | Authority |
|---|---|---|
| `transaction_understanding` | **Alone. Nothing runs beside it** | `:332` — *"Transaction Understanding establishes the base event; the other components enrich it"* |
| `party` · `item` · `payment` · `timeline` | **All four together** | `UNDERSTANDING_INTERNAL:48` — *"They are independent of one another and **may proceed in any order among themselves**"* |
| `business_context` | **Alone, after all five** | `:332` — *"'is this normal for this business' cannot be answered before knowing what **this** is"* |
| `story_builder` | **Alone, after all six** | `UNDERSTANDING_INTERNAL:50` — *"there is nothing to assemble until the six Results exist"* |

`asyncio` is the locked concurrency tool (`TECHNOLOGY_STACK.md` §Global, Workflow).

#### Why the order is load-bearing — and why breaking it is silent

`:332` gives the reason, and it is semantic rather than mechanical:

> *"The same name on a document means a different thing on a purchase than on a
> sales return, and the same date means a different thing on an invoice than on a
> receipt — so party, item, payment and timeline each receive the event nature."*

**A pipeline that ran all six in parallel would still produce a valid artifact.**
Every schema check would pass. `party` would simply have interpreted a name
without knowing whether it was buying or selling — and the wrongness would be
invisible at the seam, indistinguishable from correct work, discoverable only by
A-1, which needs a ceiling that does not exist. **This is why the order is
enforced by the signatures** (§2.1: a sibling Result is a required positional
argument) rather than by the runner remembering. A `party_understanding` that
could run first would not typecheck.

#### The concurrency trap, and why it is already closed

Four concurrent calls finish in nondeterministic order. If completion order
reached the artifact, A-7 dies.

**It cannot.** `SupportingUnderstandingData` is a Pydantic model with six **named**
fields, and `results` returns them in a hard-coded order; `all_unknowns` and
`all_conflicts` both iterate `results`; `BusinessUnderstandingObject.identified_unknowns`
derives from `all_unknowns`. There is nowhere for arrival order to be recorded.
**The artifact layer built in P2 is what makes parallelism safe here**, and that is
worth naming because it was not designed for that purpose — it fell out of
deriving everything instead of storing it.

---

### 4. Build order — and what each step buys

> **Law 5: prove correctness on one verified case before scaling. Law 17:
> implement the smallest complete solution first.**

| Step | What | Needs the API key? |
|---|---|---|
| **S0** | Sign Amendment 4 · add `ENGINE_2_AUTHORIZED` · widen four guards in `test_package.py` · add the Engine 2 wiring guard | **No** |
| **S1** | `story_builder` | **No** |
| **S2** | `pipeline`, driving `story_builder` over six injected Results | **No** |
| **S3** | Amend `ENGINE_2` §7 (the membership test) and `:8`/`:927` (the no-implementation lines) | **No** |
| — | *STOP POINT S-B: the deterministic layer is done, and everything after this costs money* | |
| **S4** | `model_backend.py` + `ReplayBackend` + `RecordingBackend` | **Yes** |
| **S5** | `transaction_understanding` — one sub-engine, one document | **Yes** |
| **S6** | `party` · `item` · `payment` · `timeline` | **Yes** |
| **S7** | `business_context` | **Yes — AND C-7 resolved** |
| **S8** | Swap `services/pipeline.py` from the stub to the real engine | — |

#### Why `story_builder` is first — four things it buys

**1. It is the only sub-engine that is finished when the model is still frozen.**
Its entire allowed power is *combine · organize · create*. Nothing in it needs a
model, which is exactly the observation Amendment 4 is built on: *"That is
assembly, not reasoning."*

**2. It pins all six Result contracts by CONSUMING them, before six producers are
written against them.** This is the real payoff and it is a Law 53 transform. Build
`story_builder` last and six sub-engines each guess what a Result must carry, and
the mismatches surface at assembly — six defects at once, at the end. Build it
first and the contract is fixed by the only component that touches all six, and
every producer afterwards has a target that already runs.

**3. It gives the artifact layer its first real workout.**
`artifacts/understanding.py` carries the engine's four hardest invariants, and at
`d7a8ed9` they have only ever been exercised by `stub.py`'s single degenerate case
— six empty Results, every score at `Decimal("0.0000")`. That is one point, and
it is the point where every ordering constraint is trivially satisfied.
`story_builder` against synthetic six-Result fixtures is where the `min`-not-`max`
strictness the module docstring **explicitly invites argument about** gets its
first honest falsification attempt:

> *"`min` rather than `max` is the strict reading of a line no document
> quantifies; it is recorded here because a strictness chosen silently is a
> decision nobody made."*

**4. It carries no risk of measuring invention.** Amendment 4's stated fear is a
seam that *"looks alive while measuring invention."* A component that cannot
invent — no model, no network, no field for a resolution — cannot produce that
failure. It is the largest piece of Engine 2 that is safe to build in the dark.

#### The fixtures `story_builder` is tested against, and where they come from

**Nothing is invented.** The locked specification supplies its own worked cases:

- `ENGINE_2:694-715` — the ₹50,000 / ₹45,000 amount mismatch, with both the
  correct output (*"Conflict: Amount mismatch detected. Status: Unresolved"*) and
  the incorrect one (*"System chooses ₹50,000"*) written out
- `:476` — a line value disagreeing with quantity × rate
- `:557` — a contradictory date sequence
- `:645` — six Results that cannot be made into a coherent narrative at all
- `:177` — a Human Business Context contradicting a document

Each becomes a permanent test. `:715` is the sharpest and is where the red-team
pass lives: **the incorrect output is wrong even when ₹50,000 turns out to be
right**, because nothing downstream can tell a choice was made.

#### Why `transaction_understanding` is the first model-backed one

`:332`, and Law 5. Every other reasoning sub-engine consumes its Result, so it is
the only one buildable next, and it is one sub-engine over one document — the
smallest version that touches reality. If a model cannot say *"this is a
purchase"* from a real GST invoice with citations that resolve, nothing built on
top of it is worth building. **That failure costs one sub-engine to discover, not
six.**

#### Why `business_context` is last

Two independent blockers, not one. It needs the model **and** it needs C-7 — an
artifact that does not exist, has no owner and appears on no `DATA_FLOW.md`
arrow. Putting it last means the other five are shipped before that argument
starts.

---

## H6. Per-phase definition of done

Not *"it works"* — the number, from GitHub CI (Law 44).

| Step | Done when |
|---|---|
| **S0** | The probe Amendment 3 used, repeated: create `engines/understanding_engine/story_builder.py` → **2 named tests fail**; add the path to `ENGINE_2_AUTHORIZED` → **all pass**; delete the path → **fail again**. Plus: `test_engine_2_authorization_admits_only_the_understanding_engine` and `test_engine_2_imports_no_ai_vendor_package` both go **red on a deliberately broken input** before they are trusted (the gate lifecycle, `CLAUDE.md` §P) |
| **S1** | `story_builder` at **coverage ≥ max(93, base)** and **mutation ≥ 93%**. All five spec-derived conflict fixtures green. **Five refusal tests red before the code and green after**: it cannot resolve a conflict, cannot drop an unknown, cannot raise confidence, cannot add an uncited fact, cannot emit accounting vocabulary |
| **S2** | `pipeline` at the same two floors. **The ordering test**: `party_understanding` invoked before `transaction_understanding` is a **typecheck failure**, not a runtime one. **The failure test**: a raising stage produces `PipelineStageError` naming that stage and preserving every earlier Result byte-identical — and produces **no artifact** |
| **S3** | `ENGINE_2` §7 carries the membership test; `:8` and `:927` are revised by a written §M amendment. `docs/ARCHITECTURE_AMENDMENTS.md` carries it |
| **S4** | `ReplayBackend` **raises** on a cache miss — proven by a test that deletes a transcript entry. A test walks every Engine 2 module's AST and fails if any names a vendor package, a vendor type or a vendor exception. **Zero network calls in the default CI run**, asserted structurally |
| **S5** | One real document → a `TransactionUnderstandingResult` whose every citation resolves into the input batch. **The falsifier: a hand-edited transcript citing a reference that is not in `citable` is REFUSED**, not trimmed |
| **S6** | Four Results, run concurrently, produce a **byte-identical artifact across 3 runs** (A-7). Same two floors |
| **S7** | Blocked. Cannot be defined until C-7 has an owner's answer |
| **S8** | `services/pipeline.py` drives the real engine; every existing `test_pipeline.py` assertion still green; `test_module_wiring.py` reports **zero new orphans** |

**A-1 — the ≥ 80%-of-ceiling number — is not on this table and cannot be.** It
needs P1. Every step above is an engineering floor; none of them is an accuracy
claim, and none may be reported as one.

---

## H7. The Build → Verify → Fix loop for this build

What **green** means here, specifically:

| | |
|---|---|
| **Build** | One step at a time from H5. Reuse first: every return type already exists in `artifacts/understanding.py` and nothing re-declares one |
| **Verify** | Test first, watch it fail for the right reason. `mutation ≥ 93%` and `coverage ≥ max(93, base)` on every new module — `do_not_mutate` covers only `*/engines/*/stub.py`, so nothing here gets a grace period |
| **Red-team** | A **separate adversarial pass per module**, matching the existing convention: Engine 1 ships `*_redteam.py` beside **seven of its nine** authorized modules (measured). The stance is fixed by `ENGINE_2:876-884` — try to make the engine **invent a fact**, **silently resolve a conflict**, **drop an unknown**, **raise confidence**, or **emit accounting vocabulary**. `:884`: *"a story that is incomplete and honestly marked is a **success**. A complete, coherent story built on one quiet assumption is a **failure**, even when the assumption is correct"* |
| **Fix** | Every defect gets a permanent test that was red before the fix. If the root is a class, the guard is written at the class (§I.12) |
| **Sequence** | loop → DONE GATE **stated** → **then** commit (Law 51) |

---

## H8. Stop Points

| | Where | What is decided |
|---|---|---|
| **S-A** | **Now — before any code** | Sign or reject Amendment 4. Confirm the §1a two-module scope, or widen it. **Nothing proceeds without this** |
| **S-B** | After S3 — the deterministic layer is complete | The last free step. **Everything after costs money.** The owner sees `story_builder` and `pipeline` working before authorizing a single call |
| **S-C** | Before S4 | The API key, the spend cap, and the eight numbers in §5. A second amendment releasing the model |
| **S-D** | Before S7 | C-7 — what artifact carries "the business's own operating history", who owns it, and which `DATA_FLOW.md` arrow it travels |
| **S-E** | Before S8 | Switching `services/pipeline.py` off the stub changes what every downstream test observes |

`CLAUDE.md` §H8 requires a stop point *"before anything touches production data."*
**N/A for this build** — Engine 2 writes to no ledger and no external system. Its
only output is an in-memory artifact handed to Engine 3.

---

## H9. Per-step risks and rollback

**A step with no undo does not get built until it has one (Law 8).**

| Step | What could go wrong | How you would know | The exact undo |
|---|---|---|---|
| **S0** | `ENGINE_2_AUTHORIZED` becomes the next place to park anything — precisely what `test_engine_1_authorization_admits_only_the_input_engine` exists to stop | A path not starting `engines/understanding_engine/` appears in it | Delete the constant and its four subtractions. Every module under the directory is refused again, immediately. **Verified by the same probe, not assumed** |
| **S1** | `story_builder` quietly improves what it assembles — §9's stated fear: *"an assembler that owns what it assembles will eventually start improving it"* | A refusal test goes green when it should be red | `git revert` one commit. `services/pipeline.py:394` still calls `StubUnderstandingEngine`. **`story_builder` is added BESIDE the stub and never replaces it until S8** — that is what makes this undo one line rather than a rescue |
| **S2** | Concurrency leaks completion order into the artifact | A-7: three runs, not byte-identical | Revert to sequential — the four enrichers in the spec's own order. Correct, slower, and the fallback is always available because order is a runner choice, never a contract |
| **S3** | A doc amendment overreaches and relaxes something | The §M record shows a prohibition removed rather than a count clarified | Amendments are append-only. Revise forward with a second amendment; never edit in place |
| **S4** | `ReplayBackend` falls through to the network on a miss | A CI job takes 40 seconds instead of 40 milliseconds, and the bill moves | Raise on miss, from the first commit. The undo is a one-line revert **plus a permanent test that deletes a transcript entry and asserts the raise** |
| **S5** | The model cites evidence that does not exist and it reaches the artifact | B-4 refuses it — **if B-4 was built first.** If B-4 is skipped, you find out at A-1, after P1, months later | B-4 lands **with** the seam in S4, never after. Its own falsifier — a hand-edited transcript with a bad citation — is written before `transaction_understanding` exists |
| **S6** | Four concurrent calls multiply a retry storm into an unbounded bill | Call count per document exceeds 6 | A hard per-transaction call ceiling in the seam, refusing rather than retrying past it. **The ceiling is an owner number** (§5, O-6) |
| **S7** | `operating_history` gets invented so the sub-engine can be finished | A type appears that no locked document names | **Do not start S7 until S-D is answered.** That is the undo: not building it |
| **S8** | Switching off the stub breaks the walking skeleton | `test_pipeline.py` goes red | One-line revert at `services/pipeline.py:156`. The stub is **never deleted** in this plan |

**The rollback that makes all of the above cheap:** `services/pipeline.py` holds
exactly one Engine 2 call site (line 394, verified). Engine 2 can be built to
completion beside the stub and switched on in one line — and off again in one.

---

## H10. Definition of Done — the DONE GATE for this build

Engine 2 is done when, and only when:

- **§C Laws** — no fabricated fact, number or threshold (24, 52) · one source of
  truth for every Result type (19) · every module reachable from
  `services/pipeline.py` (F-018's lesson) · no vendor name inside Engine 2 (21) ·
  no secret in code (22) · model output treated as untrusted (23)
- **§D thinking** — the hard problem (test a metered nondeterministic model in a
  free deterministic gate) was **transformed**, not attacked (§2.4)
- **§I / §J** — all ten test rules, including a separate red-team pass per module
  and mutation ≥ 93% on every non-stub module
- **§M** — `ENGINE_2` §7, `:8` and `:927` amended in writing before the code that
  contradicts them lands
- **The 12 gates** of `CLAUDE.md` §N, stated, before every commit
- **A-2 … A-7 green in GitHub CI**, each with its commit hash (Law 56)
- **A-1 measured at ≥ 80% of the frozen ceiling** — which requires P1, and is the
  one line on this list that no amount of engineering can tick

---

## Contradictions found between the locked documents

Every one was found while writing this plan. **None is resolved here** — §E.7:
record it, do not fix it.

### C-1 · The base commit predates the amendment this plan is written for
`d7a8ed9` contains no `Amendment 4` in `CLAUDE.md` and no `ENGINE_2_AUTHORIZED`
in `tests/unit/test_package.py` (both measured, 0 matches). They exist only in
the shared checkout's working copy. **Impact:** the exact diff in §1a must be
re-derived against whatever commit carries the signed amendment.

### C-2 · Two amendment series share numbers, and one source file cites the wrong one
`CLAUDE.md` §P runs **Amendments 1–4** (build-freeze scope).
`docs/ARCHITECTURE_AMENDMENTS.md` runs **Amendments 2–8** (architecture). They
collide:

| Number | `CLAUDE.md` §P | `docs/ARCHITECTURE_AMENDMENTS.md` |
|---|---|---|
| 2 | Build freeze, scoped release | `WaitingForApproval` state |
| 3 | Engine 1 authorization | NOT PROPOSED: `Cancelled` |
| 4 | **Engine 2 release** (draft) | **`Human Instruction` artifact: deleted** |

**And the collision has already produced a live mis-citation in source.**
`src/accountant_dad/engines/input_engine/pipeline.py:136` reads
*"`ARCHITECTURE_AMENDMENTS.md` **Amendment 5** (approved 2026-08-06) removed the
cause… `Provenance.confidence` and `FieldConfidence.confidence` are now
`ConfidenceOrUnmeasured`."* That is `ARCHITECTURE_AMENDMENTS.md`
**Amendment 6** — *"an absent-measurement state on `Provenance.confidence`"*
(line 304). **Amendment 5** (line 250) is the sub-engine membership test.
`src/accountant_dad/confidence.py` carries the same wrong number. **Out of scope
here — this task may not touch `src/`.**

### C-3 · A signed Amendment 4 falsifies two lines of the locked Engine 2 spec
`ENGINE_2:8` — *"Specification only — no implementation. No code, no libraries,
no AI models, no LLM pipelines, no OCR, no APIs, no databases, no dependencies."*
`ENGINE_2:927` — *"[x] No implementation exists."*
The moment `story_builder.py` lands, both are false. **Law 20 and §M require the
document be revised, never worked around in code.** Engine 1 hit this exact wall
and it cost a day (F-010). **S3 exists for this.**

### C-4 · *"Exactly seven"* counts Results, not files — and nothing says so yet
`ENGINE_2:292` states *"exactly seven"* sub-engines and `:307-309` forbid adding,
removing or merging one. Engine 2 will ship **ten modules**. This is F-010
repeating verbatim: Engine 1 shipped nine against *"exactly four"* and the
repository could not say whether the lock was violated.
`COMMUNICATION_RULES_UNDERSTANDING_INTERNAL.md` Rule 1 already supplies the
predicate — *publishes one of the seven named Results* — but **Engine 2's §7 does
not carry it**, where Engine 1's §7 now does. It must be added before the code,
not after.

### C-5 · Assembly is a sub-engine in Engine 2 and forbidden as one in Engine 1
`ENGINE_1:384` — *"No new assembler sub-engine is created."*
`ENGINE_2` §8.7 — `story_builder` **is** a sub-engine and its whole job is
assembly. Both are correct and locked; the asymmetry is real and deliberate. It
is recorded because an engineer applying Engine 1's classification to Engine 2
would misfile `story_builder` and create the `assembly.py` that N-5 forbids.

### C-6 · `business_context` may not read the accounting configuration, and needs something like it
`ENGINE_2:592` forbids reading the chart of accounts, ledger masters,
registration status and accounting policy — those belong to Engine 3's
`company_understanding`. `:583` requires it to record *"whether the party is
recurring and whether the pattern is normal for this business."* Both are locked;
the boundary between "this business's operating pattern" and "this business's
accounting configuration" is **not drawn anywhere**. C-7 is the sharp end of it.

### C-7 · An input with no artifact, no owner and no arrow — THE LARGEST HOLE
`ENGINE_2:573` and `SUB_ENGINE_RESPONSIBILITIES.md:188` both say
`business_context` receives *"the business's own operating history."*

**Measured across all 46 documents in `docs/` that existed before this one: those
are the only two occurrences of the phrase.** No artifact carries it.
`DATA_FLOW.md` draws no arrow for it.
`ENGINE_2` §4's input contract is Document Evidence Objects and nothing else. It
is not the Brain — `ENGINE_2` and both its communication contracts mention the
Brain **zero times** (measured), and the Brain holds GST/ICAI/Companies Act
knowledge, not one company's transaction history.

**So one of the seven sub-engines is specified to consume an input that does not
exist.** This blocks `business_context` **independently of the API key**, and no
amount of engineering closes it — it is a missing contract and needs the owner.

### C-8 · The OpenRouter fallback has no trigger, and a confidence threshold may not become one
`TECHNOLOGY_STACK.md` §Engine 2 lists OpenRouter as *"fallback only"* and gives
it **no trigger** — identical to Engine 1's Gemini Vision fallback, whose note
says the blocker *"is not a missing NUMBER… Decision **A7** and
`MEASUREMENT_FRAMEWORK.md` §10 hold that confidence gates NOTHING until the
separation test passes, so setting that number would be forbidden even if the
owner supplied one today."* **`ARCHITECTURE_AMENDMENTS.md` Amendment 8 was never
carried into Engine 2's row**, and the same routing decision is owed. N-4 declines
to build it.

### C-9 · CLAUDE.md Law 54 calls "Understanding" undefined; `ACCOUNTING_DEFINITIONS.md` §2 defines it
Law 54's standing-debt table lists **Understanding — Engine 2's entire output** as
undefined and unmeasurable. `ACCOUNTING_DEFINITIONS.md` §2 defines it precisely,
with a four-step measurement and a threshold. §P reconciles them — *"Measurement
framework · definitions · dataset spec — ✅ Written — awaiting sign-off"* — so
the debt is **a signature, not a definition**. Recorded because this blueprint's
entire finish line rests on that definition, and a reader who trusts Law 54's
table would conclude Engine 2 cannot be specified at all.

### C-10 · spaCy is in the locked stack with no stated purpose
`TECHNOLOGY_STACK.md` §Engine 2 lists spaCy for *"linguistic processing."* No
locked document says what Engine 2 uses it for, which sub-engine owns it, or what
it would decide. It is the **only** Engine 2 tool the API key does not block, so
it is the one that will get used to fill a gap simply because it is available.
N-6 declines. It needs a purpose before it needs an install.

### C-11 · The blueprint disagrees with itself about whether Engine 2 consults the Brain
`BLUEPRINT:99` — *"Brain stub | P3 | Brain interface contract (P2) | **Engine
stubs 2–6**."* `BLUEPRINT:100`'s own row for the engine stubs names only the
Application Layer and the artifact schemas. `stub.py` already records this
(*"The two rows disagree, and nothing is resolved here"*) and declines to consult
it. This plan declines identically (N-8) and records that the disagreement is now
**two components old** and still unresolved.

---

## The owner decisions this plan is waiting on

Drafted in `OWNER_DECISION_QUEUE.md`'s shape — **each is a yes/no/pick-one with
the engineering already done behind it**, per that file's standing rule that
"shrink" means doing everything up to the decision.

| # | Decision | Blocks | Failure mode if guessed |
|---|---|---|---|
| **O-1** | **Sign or reject Amendment 4**, and confirm the §1a two-module scope | Everything | — |
| **O-2** | **Gemini API key + authorized spend** | S4–S8 | — |
| **O-3** | **C-7** — which artifact carries "the business's own operating history", who owns it, which arrow it travels | S7 | An invented type nobody specified, inside a locked engine |
| **O-4** | **Temperature · seed · top-p · max output tokens** | S4 | A number chosen because it looked reasonable — exactly what §P forbids |
| **O-5** | **Model version pin · request timeout · retry count** | S4 | An unpinned model makes the same commit produce two artifacts (A-7 dies) |
| **O-6** | **Hard per-transaction call ceiling** | S4, S6 | An unbounded bill from a retry storm |
| **O-7** | **The evidence-confidence aggregation rule** — many documents, many field scores, one number | S1 | Law 54's undefined term settled silently by the engineer. `stub.py` already refuses to |
| **O-8** | **The OpenRouter fallback trigger** (C-8) — a routing decision, not a number | N-4 | A confidence threshold, which Decision A7 forbids |

**Only O-1 and O-7 block S1.** O-7 is settled by passing the number in (§2.2), so
in practice **O-1 alone gates the entire deterministic layer.**

---

## Cost and benefit

> **Every figure below is labelled. One is derived and exact. The rest are
> UNMEASURED and no proxy is offered for them (Law 24, Law 52).**

### Model calls per document — DERIVED, exact, architecturally pinned

```
transaction_understanding   1
party_understanding         1
item_understanding          1     <- these four concurrent
payment_understanding       1
timeline_understanding      1
business_context            1
story_builder               0     <- no model, by design
                          ───
                            6  calls per TRANSACTION
```

**Six, and independent of how many documents the transaction has.** That is a
designed property, not an accident. `ENGINE_2:157` sends the whole batch to the
engine, and each sub-engine takes the whole batch in one call — so the naive
per-document shape, **6 × N**, never happens. The cross-document reconciliation
that would otherwise need extra calls is already assigned: `:165` gives it to
`story_builder`, which makes zero.

### What drives the number

| Driver | Effect | Can it be reduced? |
|---|---|---|
| **6 reasoning sub-engines** | The whole call count | **No.** `ENGINE_2:292` — *"exactly seven"*; `:307-309` — do not add, remove or merge. Merging two sub-engines to halve the calls is an **architecture change requiring an amendment**, not an optimisation. Stated plainly because it is the first idea anyone will have |
| **Retries** on schema-validation or citation-check failure | Multiplies 6 by an unknown factor | Not without measuring it first (Law 6). **UNMEASURED** |
| **Clarification round trips** (§12) | New information → a **new artifact version** → a full re-run → **+6** | No — immutability requires it |
| **Batch size N** | Calls stay at 6. **Input tokens scale with N**, because all documents appear in all six prompts | Yes, and **this is where the money actually is** — not in the call count |

**The last row is the finding.** Optimising call count is optimising a
non-bottleneck. Six calls is fixed by the architecture; token volume is 6 × (the
whole batch) and is the only variable anyone can move.

### What is UNMEASURED, and exactly what would settle it

| Quantity | Status | The cheapest experiment that settles it |
|---|---|---|
| Input tokens per call | **UNMEASURED** | Tokenise the 25 golden-set documents. **Needs no API key** — it needs the golden set, which is P1's |
| Output tokens per Result | **UNMEASURED** | One recorded run over one document. Needs O-2 |
| Price per transaction | **UNMEASURED** | The two above × the published rate. **No price appears in any repository document**, and quoting one from memory would be fabrication |
| Retry multiplier | **UNMEASURED** | Count refusals across one recorded run of 25 documents |
| Latency per transaction | **UNMEASURED** | The critical path is `transaction` → 4 concurrent → `business_context` → `story_builder` = **4 sequential model round trips**, not 6. That structure is derived; the wall-clock number is not |

### The benefit — the idiot index of this plan

| | Model calls | Spend | What it delivers |
|---|---|---|---|
| **S0–S3** (deterministic layer) | **0** | **0** | 2 of 7 sub-engines · the runner · **100% of the artifact-integrity invariants** — conflict preservation, unknown preservation, confidence ceilings, vocabulary refusal · every acceptance criterion except A-1 and A-8's price half |
| **S4–S8** (reasoning layer) | 6/transaction | UNMEASURED | The other 5 sub-engines · A-1, which needs P1 anyway |

**The cheap half delivers every property the engine exists to guarantee.** Engine
2's stated failure modes (`:876-884`) are *inventing a fact · silently resolving a
conflict · dropping an unknown · raising confidence · using accounting
vocabulary*. **Every one of the five is caught in the layer that costs nothing.**
The model supplies the content; the free layer is what stops the content being
believed more than it deserves.

That is the shrink-before-you-solve move, and it is why S-B is a stop point: the
owner gets to see the guarantees working before authorising the first rupee.

---

## Related documents

- [`ENGINE_2_UNDERSTANDING_ENGINE_RULES.md`](ENGINE_2_UNDERSTANDING_ENGINE_RULES.md) — the locked specification this plan executes
- [`COMMUNICATION_RULES_UNDERSTANDING_INTERNAL.md`](COMMUNICATION_RULES_UNDERSTANDING_INTERNAL.md) — the seven sub-engines' internal contract; the source of the membership test in §1d
- [`COMMUNICATION_RULES_UNDERSTANDING_ENGINE.md`](COMMUNICATION_RULES_UNDERSTANDING_ENGINE.md) — the outbound boundary to Engine 3
- [`SUB_ENGINE_RESPONSIBILITIES.md`](SUB_ENGINE_RESPONSIBILITIES.md) §2 — the canonical snake_case names §1b quotes
- [`TECHNOLOGY_STACK.md`](TECHNOLOGY_STACK.md) §Engine 2 — the six tools, five of them behind the one seam
- [`ACCOUNTING_DEFINITIONS.md`](ACCOUNTING_DEFINITIONS.md) §2 — the definition that makes H1 measurable
- [`MVP_IMPLEMENTATION_BLUEPRINT.md`](MVP_IMPLEMENTATION_BLUEPRINT.md) — condition 7 of nine, and the phase order
- `src/accountant_dad/pdf_backend.py` — **read this before implementing §2.3.** The seam design is its design
- `src/accountant_dad/artifacts/understanding.py` — the complete artifact layer this plan consumes and never rebuilds
- `src/accountant_dad/engines/input_engine/pipeline.py` — the runner §2.5 is modelled on
