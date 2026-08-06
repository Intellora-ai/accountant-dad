# Architecture Amendments

> **Status is stated per amendment. Read it — the amendments are not all in the same state.**
> Locked documents are updated only after architectural review and written approval, per
> `CLAUDE.md` §M.

> ### ⚠️ CORRECTION 2026-08-06 — this header used to say "PROPOSED, NOT APPLIED"
>
> It also said *"No locked document has been modified."* **That is no longer true, and leaving
> it would have been a fabricated status** (Law 24). **Amendment 5**, below, is applied: it
> modified `ENGINE_1_INPUT_ENGINE_RULES.md`, a locked level-3 specification, additively and
> under the owner's delegated authority of 2026-08-06.
>
> Amendments **2** and **3** are unchanged and remain unapplied. Amendment **4** was already
> approved and applied on 2026-08-03 while the header still claimed otherwise — so the header
> was already stale before Amendment 5 made it wrong.

> ### ⚠️ NUMBERING COLLISION — flagged, not resolved
>
> `CLAUDE.md` §P now records **"Amendment 2 — Build freeze, scoped release"** (approved 2026-08-03).
> This file already used **Amendment 2** for `WaitingForApproval`, which is still unapproved.
> **Two different amendments share the number 2 across two documents.** Renumbering an
> amendment that five documents already reference would be a silent change, so it is
> **flagged here and left alone** pending a decision.

---

## Why this file exists

`CLAUDE.md` §M requires that no frozen document changes without a written amendment recording what changed, why, what failure forced it, the trade-off, and what now guards it.

Previously the intent was to write amendments directly into the locked documents. That was changed on your instruction:

> *"Keeps the locked documents actually locked. Gives you one review point before changing the constitution."*

**Corrected 2026-08-06.** This line used to read *"Nothing here is in force."* It was true when written and is not true now — Amendment 4 is applied and Amendment 5 is applied. **Read the Status row of each amendment; do not read a blanket claim from this section.** Amendments that are still proposals say so, and the documents depending on them describe the current locked behaviour alongside the proposed behaviour.

---

# Amendment 2 — `WaitingForApproval` state

> Amendment 1 is the CI scaffolding exemption, recorded in `CLAUDE.md` §P.

| | |
|---|---|
| **Status** | ⬜ **PROPOSED — awaiting approval** |
| **Affects** | `DATA_FLOW.md` §14 · `SYSTEM_INVARIANTS.md` INV-4 |
| **Raised** | 2026-08-03, during Application Layer design |

## What changed

**Old rule** — the transaction state machine, `DATA_FLOW.md` §14 and INV-4:

```text
Input → Understanding → Accounting → Clarification → Validation → Execution → Completed
                                                                            ↘ Failed
```

**New rule** — one state added between `Validation` and `Execution`:

```text
Input → Understanding → Accounting → Clarification → Validation
            → WaitingForApproval → Execution → Completed
                                                    ↘ Failed
```

`WaitingForApproval` is entered **only** when the Validation Decision is `Approved With Warning`. A plain `Approved` decision moves directly to `Execution`. Nothing else may enter this state.

## Why

Three locked documents already require the Application Layer to hold work until a human releases it:

| Source | Text |
|---|---|
| `COMMUNICATION_RULES_VALIDATION_ENGINE.md:61` | *"Nothing — until the Application Layer releases it after human attention."* |
| `COMMUNICATION_RULES_VALIDATION_ENGINE.md:69` | *"The Application Layer. Engine 6 cannot hold a workflow gate."* |
| `ENGINE_6_EXECUTION_ENGINE_RULES.md:147` | *"Nothing — until the Application Layer releases it after human attention."* |
| `DATA_FLOW.md:283` | *"an `Approved With Warning` decision only after the Application Layer releases it"* |

**But the state machine has nowhere for that work to wait.** The hold is required in four places and representable in none.

## What failure forced it

Designing the Application Layer made the gap unavoidable. A transaction that is `Approved With Warning` is:

- no longer in `Validation` — the engine has finished and produced its artifact
- not yet in `Execution` — Engine 6 has received nothing and must not begin

Under INV-4 a transaction is in **exactly one state at any moment**. Without a state for the hold, such a transaction is in **no state**, which the invariant forbids.

The alternative was to hold the work inside the Application Layer without representing it. Your ruling closed that off:

> *"Do NOT invent a hidden queue. If work pauses, the state machine must represent that pause."*

## The trade-off

| Gained | Lost |
|---|---|
| The transaction state machine becomes **total** — every reachable situation has exactly one state | One more state to implement, test and reason about |
| The pause is **visible and queryable** rather than hidden inside orchestration code | The locked state machine changes, so every document quoting it must be re-checked |
| `Approved With Warning` becomes structurally distinct from `Clarification Required`, which `COMMUNICATION_RULES_VALIDATION_INTERNAL.md:164` requires | A transaction can now sit indefinitely awaiting a human — an operational concern that did not previously exist in the model |

**Not chosen: removing `Approved With Warning`.** That was the other option you offered. Rejected because `ENGINE_5_VALIDATION_ENGINE_RULES.md:439` states `risk_assessment` has **no output path without it** — *"some entries are correct and still should not be posted unattended."* Removing the status would delete a validator's only means of expression.

## What now guards it

| Guard | Where |
|---|---|
| Only `Approved With Warning` may enter `WaitingForApproval` | `APPLICATION_LAYER_INVARIANTS.md` AL-INV-9 |
| Only `release_waiting_for_approval()` may leave it toward `Execution` | `APPLICATION_LAYER_API.md` |
| No engine may enter, leave or observe this state | `APPLICATION_LAYER_INVARIANTS.md` AL-INV-4 |
| A transaction is in exactly one state, including this one | `APPLICATION_LAYER_INVARIANTS.md` AL-INV-2 |
| Engine 6 never learns the gate existed | `COMMUNICATION_RULES_VALIDATION_ENGINE.md:71`, unchanged |

## Approval

```
Proposed by : Claude, 2026-08-03
Approved by : ⬜ NOT YET APPROVED
Applied     : ⬜ NOT APPLIED to DATA_FLOW.md or SYSTEM_INVARIANTS.md
```

---

# Amendment 3 — NOT PROPOSED: `Cancelled`

Recorded so the decision is not re-litigated.

A `Cancelled` state was requested during Application Layer design. **It is not proposed and does not exist.**

Your ruling:

> *"If a state is not in the locked state machine, it does not exist. Never invent execution states because they 'seem useful.' That discipline is exactly what prevents architecture drift."*

No locked document mentions cancellation. Nothing in the Application Layer design supports, implies or leaves room for it. If cancellation is ever wanted it arrives as its own amendment, with its own answers to: what happens to artifacts already produced (they are immutable and cannot be deleted), whether a cancelled transaction may resume, and what an external system already holding a posted voucher is told.

```
Status : ❌ NOT PROPOSED — deliberately absent
```

---

# Amendment 4 — `Human Instruction` artifact: **deleted, never existed**

| | |
|---|---|
| **Status** | ✅ **APPROVED 2026-08-03** |
| **Affects** | `FORWARD_DEPENDENCY_INVENTORY.md:94` — the *Unsettled* row only |
| **Does NOT affect** | `SYSTEM_INVARIANTS.md` INV-4 — **unchanged, not weakened, no carve-out** |

## What changed

**Old rule** — `FORWARD_DEPENDENCY_INVENTORY.md:94`:

> *"Recommendation: keep the lock, add a separate **Human Instruction** artifact **owned by the Application Layer** … 'Bought laptops for the design team' is evidence; 'Post this tomorrow' is an instruction."*

**New rule** — **there is no Human Instruction artifact.** The recommendation is withdrawn. Six canonical artifacts remain six.

## Which wins, and why it was never a real conflict

```
SYSTEM_INVARIANTS.md          precedence level 1     LOCK
FORWARD_DEPENDENCY_INVENTORY  precedence level 2     recommendation, not a lock
```

INV-1: **locks win.** The FDI row proposed exactly what INV-4's table forbids — *"It never owns: any decision · any artifact · any confidence…"* — so it was dead as written.

## The assumption that created the conflict

```
Fact        : a human sometimes types scheduling intent
Constraint  : INV-4 — the Application Layer owns no artifact  (locked, level 1)
Assumption  : an instruction has to be an artifact             ← THIS IS THE DEFECT
```

An artifact in this system is **immutable · versioned with a parent chain · owned by exactly one engine · consumed downstream · part of the accounting audit trail.**

Run *"post this tomorrow"* against that list:

| Property | Needed? |
|---|---|
| Immutable | **No** — the human can change their mind |
| Versioned, parent chain | **No** |
| Consumed by an engine | **No** — the FDI itself says *"Never binding on any engine"* |
| Part of the accounting audit trail | **No** |

**Zero of four.** A thing no engine may consume, that carries no accounting meaning, and that is allowed to change **is not an artifact.** Calling it one is what manufactured the conflict.

## It was already owned — look at INV-4's own left column

> *"Creating the Transaction ID · starting engines · routing artifacts · **lifecycle** · retrying · **coordinating state transitions** · deciding a transaction is complete"*

*"Post this tomorrow"* is **when a state transition fires.** That is already inside what the Application Layer owns. It needs no new artifact — it is **a field on orchestration state the Application Layer already manages.**

## The second half — classification — is deleted too

*"Who decides which is which?"* is a trap. If an engine classifies it, fine. **If the Application Layer classifies it, that is reasoning, which INV-4 also forbids** — one violation swapped for another.

**So the split happens at INPUT, never by inference:**

```
┌─ business context box ──┐   free text  →  Engine 1, Human Business Context, EVIDENCE
└─ scheduling control ────┘   structured →  Application Layer orchestration state

Zero classification. Zero ambiguity. Zero reasoning in the Application Layer.
```

The conflict existed only because one free-text box was assumed, forcing something downstream to interpret it.

**Failure mode, and why it is correct:** a human types *"post this tomorrow"* into the context box anyway. It is stored **verbatim** as Human Business Context under Engine 1 — evidence that the human said it, never truth, never rewritten — and it has **no scheduling effect.** The system ignores it. That is already the rule (`ENGINE_1`, evidence carries its origin permanently).

## The trade-off

| Gained | Lost |
|---|---|
| **Zero amendments to any locked document.** INV-4 stands untouched | *"Post this tomorrow"* needs a scheduling control in the interface, which does not exist yet |
| Six canonical artifacts stay six; no ripple across the document set | A reader of `FORWARD_DEPENDENCY_INVENTORY.md:94` must be told where the artifact went |
| The architecture freeze is unblocked | — |

## What would prove this wrong

**An instruction that is genuinely neither workflow nor evidence — one needing immutability and an audit trail.**

Closest candidate: *"the client authorized posting to a closed period."* But that is not an instruction, it is **evidence of an authorization**, and it has two existing homes — Human Business Context under Engine 1, or a Clarification Answer under Engine 4. Both artifacts already exist with correct owners.

No case requiring a new artifact could be constructed. **If one is found, it kills this amendment.**

## What now guards it

| Guard | Where |
|---|---|
| Six canonical artifacts, Application Layer owns none | `APPLICATION_LAYER_RESPONSIBILITY_MATRIX.md` · conformance predicate at P2 |
| The Application Layer never classifies free text | `APPLICATION_LAYER_INVARIANTS.md` — it performs no reasoning |
| Human free text is evidence, stored verbatim, never binding | `ENGINE_1_INPUT_ENGINE_RULES.md`, unchanged |
| Scheduling is orchestration state, not an artifact | `APPLICATION_LAYER.md` |

## Approval

```
Proposed by : Claude, 2026-08-03
Approved by : The user, 2026-08-03
Applied     : ✅ FORWARD_DEPENDENCY_INVENTORY.md:94 moved Unsettled → Settled
              ✅ ARCHITECTURE_AUDIT.md Issue 1 closed
              ✅ APPLICATION_LAYER_RESPONSIBILITY_MATRIX.md conflict section closed
              ⬜ SYSTEM_INVARIANTS.md — DELIBERATELY UNTOUCHED
```

---

# Amendment 5 — "Exactly four sub-engines": the membership test, stated

| | |
|---|---|
| **Status** | ✅ **APPLIED 2026-08-06** — by delegated engineering authority, see Approval |
| **Affects** | `ENGINE_1_INPUT_ENGINE_RULES.md` §7 and §10 — **additive only** |
| **Raised** | 2026-08-06, resolving `KNOWN_FAILURES.md` **F-010** |

## What changed

**Old rule** — `ENGINE_1_INPUT_ENGINE_RULES.md:353`, unchanged and still in force:

> *"The Input Engine contains **exactly four** sub-engines"* — Cleaner · Reader · Parser · Confidence.
> *"Do not add new sub-engines. Do not remove sub-engines. Do not merge responsibilities."*

**New rule** — nothing above is altered. One section is **added** to §7, and one checklist line to §10:

> **A component is a sub-engine if, and only if, it produces one of the four parts the parent engine combines into the Document Evidence Object.**
>
> Every Engine 1 component is exactly one of: a **sub-engine** · the **parent engine's own machinery** · an **engine-level facility**.

**This subtracts nothing.** The count stays four, the prohibition on adding a fifth stays absolute, and no component is reclassified into the sub-engine set. What is added is the predicate that decides membership — which the document previously left unstated.

## Why

The clause stated a count without stating what it counted. That is Law 52 unmet inside a locked document: a number with no procedure for obtaining it. Two readings were both defensible from the text, and the repository sat on the ambiguity for a day.

**The test is not invented here. It is quoted.** `:399` already labels the four output contracts *"the four parts the parent engine combines."* The amendment promotes that sentence from a table caption to the membership rule it always implied.

## What failure forced it

Engine 1 ships **nine** source files. Read as a sub-engine count, that is five too many and a level-3 lock is violated. The reading was never sound, and three independent facts kill it:

| Fact | Where |
|---|---|
| The document forbids implementation outright — *"Specification only — no implementation. No code, no libraries … no pipelines"* | `ENGINE_1_INPUT_ENGINE_RULES.md:8` |
| Engine-level work that is **not** sub-engine work already exists by construction: assembly must happen, and *"No new assembler sub-engine is created"* | `ENGINE_1_INPUT_ENGINE_RULES.md:384` · `SUB_ENGINE_RESPONSIBILITIES.md` §1 boxed note |
| The parent is a fifth **row** in the Decision Authority table with its own `Owns` column — a component, and not a sub-engine | `ENGINE_1_INPUT_ENGINE_RULES.md:95` |
| The system-wide count behaves identically: *"45 components: 6 engines, 39 sub-engines"* — and **assembly is not among the 45**, though the architecture requires it to happen | `MVP_ARCHITECTURE.md:57` |

A count written by a document that forbids code from existing cannot have been a count of code.

**The third category was already in use, unnamed.** The last row above is the check on the whole amendment: the semantic tree has always excluded engine-level machinery that the architecture nonetheless requires to exist. This amendment names that exclusion instead of inventing one, and the 45 is unchanged.

## What decides the hard case

`classification` is the one that could not be settled by inspection alone. It is authorised by name (`CLAUDE.md` §P Amendment 3) yet appears in no sub-engine map. The artifact settles it:

```
DocumentEvidenceObject  =  identity · document_id · source_references
                           structured_document · human_business_context? · confidence_report
```

**No document-type field. No fifth component.** Its output therefore cannot be one of the four parts, so it is not a sub-engine — it is a facility, alongside configuration loading and the calibration record.
# Amendment 6 — an absent-measurement state on `Provenance.confidence`

> Continues **this file's** sequence, after Amendment 4. The numbering collision flagged
> at the top of this file — `CLAUDE.md` §P also has an Amendment 2 — is **unchanged and
> unresolved here**; renumbering is not this amendment's to do.

| | |
|---|---|
| **Status** | ✅ **APPROVED 2026-08-06** |
| **Affects** | `src/accountant_dad/confidence.py` · `src/accountant_dad/artifacts/evidence.py` — `Provenance.confidence`, `FieldConfidence.confidence`, `DocumentEvidenceObject._every_reading_is_scored_and_the_scores_agree` · `docs/CONFIDENCE_SPECIFICATION.md` §3.4 |
| **Does NOT affect** | `SYSTEM_INVARIANTS.md` INV-11 — **six provenance attributes, none optional, unchanged and not weakened** · the `Confidence` type itself — **still `Decimal` only, [0.0000, 1.0000], ≤ 4 places** · the artifacts of Engines 2–6, none of which use `Provenance` |
| **Raised** | 2026-08-06, from three red tests on the MVP's primary input |

## What changed

**Old rule** — `evidence.py:118-130`, restating `SYSTEM_INVARIANTS.md:243-252` and
`CONFIDENCE_SPECIFICATION.md` §3.3:

```python
class Provenance(BaseModel):
    ...
    confidence: Confidence        # Decimal, [0.0000, 1.0000], ≤ 4 places
```

`Confidence` admits **only** a number. So a value that was genuinely read, and that
nothing scored, has **no representable provenance** — and by
`ENGINE_1_INPUT_ENGINE_RULES.md:245` (*"A value carried without all three is not evidence
and must not be emitted"*) it must therefore not be emitted at all.

**New rule** — two slots, and only these two, now record **either** a measurement **or**
the stated absence of one:

```python
confidence: ConfidenceOrUnmeasured    # Provenance.confidence
confidence: ConfidenceOrUnmeasured    # FieldConfidence.confidence
```

```
ConfidenceOrUnmeasured  =  Confidence            a Decimal in [0.0000, 1.0000]
                        |  UNMEASURED            a distinct sentinel class
```

Three things this is **not**, each stated because each was the obvious wrong answer:

| Not | Why it was refused |
|---|---|
| `Confidence \| None` | `None` already means three other things in this pipeline — `TextRegion.extraction_confidence` (no recogniser ran), `RegionReading.text` (unread), the absence of a `HumanBusinessContext`. A fourth meaning on a fourth slot is how a distinction dies. |
| A widened `Confidence` | The owner's ruling defines confidence as *"a normalized Decimal score."* The absence of a score is not a score. Widening it would have let **every** artifact in the system carry "not measured" wherever a number belongs, including five schemas that never asked for it. |
| An optional attribute | INV-11 is untouched. The sentinel makes the **value** absent; the **attribute** is still mandatory, still six, still `extra="forbid"`. |

**The agreement rule is extended, never exempted.** `evidence.py:337-353` refuses a
detected field with no entry in the Confidence Report, and refuses an entry that
disagrees with the field's own provenance. Both still run for an unscored field. What
"agreement" means now has one more way to **fail**:

```
both unmeasured        AGREE      neither claims a score; there is nothing to contradict
both measured, equal   AGREE      unchanged
both measured, differ  DISAGREE   unchanged
one of each            DISAGREE   NEW — one side asserts a number the other says was
                                  never taken. This is the precise shape of the bug the
                                  sentinel exists to prevent, so it fails loudest.
```

Decided by `isinstance`, never by `is` and never by `==`: `==` between a `Decimal` and
the sentinel answers `False` only by falling through two `NotImplemented`s to identity —
the right answer reached by accident, from a rule about neither type.

## Which doc / section

| File | Change |
|---|---|
| `src/accountant_dad/confidence.py` | **Added** `UnmeasuredType`, the `UNMEASURED` instance, `ConfidenceOrUnmeasured`, `records_the_same_measurement`. `Confidence`, `MIN`, `MAX`, `CONFIDENCE_PLACES` and `_exactly_a_decimal_in_range` are **unchanged** — the new validator delegates to the existing one, so both types enforce one scale (Law 14, Law 19). |
| `src/accountant_dad/artifacts/evidence.py` | `Provenance.confidence` and `FieldConfidence.confidence` retyped. The agreement check now calls `records_the_same_measurement`. |
| `src/accountant_dad/engines/input_engine/pipeline.py` | An unscored mapping now becomes a real `DetectedField` carrying `UNMEASURED`, instead of being dropped. |
| `docs/CONFIDENCE_SPECIFICATION.md` §3.4 | Records this amendment by name, so a locked document no longer describes a schema the code has moved past. |

## Why

`reader.read_pdf_text_layer` sets `extraction_confidence=None` on **every** region it
produces, deliberately (`reader.py:255-259`):

> *"`None` is NOT zero confidence and NOT full confidence — it is the absence of a
> measurement."*

A PDF text layer is **transcribed, not recognised**. No instrument runs, so no instrument
produces a score. There is nothing wrong with the document and nothing wrong with the
reading — the score simply does not exist.

**And a PDF text layer is the MVP's primary input.** `CLAUDE.md` §B.7 puts the MVP inside
Tally and the Indian GST regime, where documents are overwhelmingly PDF.

**No honest number exists to put there**, and this is why the fix had to be a *type* and
not a *value*:

| Candidate | Why it is a lie |
|---|---|
| `1.0000` | The default `ENGINE_1_INPUT_ENGINE_RULES.md:625` forbids **by name** — *"never to a default 'good enough' value."* |
| `0.0000` | Asserts a measured worthlessness **nobody measured**. On a scale where low confidence is the most alarming signal in the artifact, this manufactures the alarm. |
| A looked-up parameter | None of the sixteen in `ENGINE_1_CONFIDENCE_PARAMETERS.md` covers this case, and all sixteen are `UNSET` regardless. |

Law 54 is explicit: never invent the definition. So the absence was **named** instead of
filled in.

## What failure forced it

Three tests, red on `99f62bf`, all on this one root cause:

```
tests/integration/test_engine1_end_to_end.py::
    test_every_extracted_value_that_crosses_the_boundary_carries_source_confidence_and_uncertainty
tests/unit/test_conformance_registry.py::
    test_every_value_the_engine_extracted_carries_where_it_came_from
tests/unit/test_conformance_registry.py::
    test_the_artifact_carries_provenance_for_the_evidence_it_states
```

The third one's failure message is the whole defect in one line:

> *"the artifact carries no Provenance anywhere, so nothing crosses the Input →
> Understanding boundary with an origin attached."*

The mechanism, measured rather than reasoned about:

```
reader.read_pdf_text_layer   →  every region: extraction_confidence = None
pipeline.detected_fields     →  `if field.extraction_confidence is not None` — SKIPS them
StructuredDocument           →  detected_fields = ()
DocumentEvidenceObject       →  zero Provenance objects, on the MVP's primary input
```

Every extracted value crossed the Input → Understanding boundary as a bare `str` inside
`extracted_text`, carrying **no source, no confidence and no uncertainty of its own** —
which is what `COMMUNICATION_RULES_INPUT_ENGINE.md:111` forbids stripping and what
`ENGINE_1_INPUT_ENGINE_RULES.md:245` forbids emitting.

The skip was **correct given the schema** — `pipeline.py`'s own docstring said so, and
`test_an_unscored_reading_is_skipped_rather_than_given_an_invented_score` pinned it, with
the note that changing it *"needs a §M amendment to a frozen schema, and it must not
arrive quietly."* **This is that amendment.** The schema was the defect, not the skip.

## Why not share one sentinel with `measurement.AbsentType`

The F-005 resolution (`measurement.py:147-170`) established this exact shape one module
away. It is copied as a **pattern**, never as a shared object (Law 53 — copy the
principle, never the mechanism). Two reasons, one of them mechanical and unarguable:

1. **The two facts differ, and merging them destroys what both types exist to keep.**
   `ABSENT` says a whole signal **category was never produced** — nothing was attempted.
   `UNMEASURED` says a reading **exists, is real, and travels into the artifact**, and
   only its score is missing. One shared class makes `isinstance(x, AbsentType)` answer
   yes to both — the exact collapse Law 24 forbids and the reason `measurement.py:41-59`
   refuses to let two facts wear one shape.
2. **Sharing is a circular import, measured not assumed.** `measurement.py:138` imports
   `DocumentId` from `artifacts.evidence`; `artifacts.evidence` imports `confidence`. So
   `confidence → measurement → evidence → confidence` does not import at all.

Layering agrees without needing either argument: `measurement.py` is an Engine 1
calibration store, and a type six artifact schemas depend on cannot be owned by one
engine's internal module (INV-10 — one owner per concept).

**And it is not `confidence_report.ReadingState` either.** That enum's `READ_BUT_UNSCORED`
fixed the *Confidence Report's* view of a **region**. This fixes the *provenance* of a
**named field**. Different object, different level, different owner — `ReadingState` is
derived from two fields and stored nowhere, and it cannot sit in a schema slot.

## The trade-off

| Gained | Lost |
|---|---|
| The count becomes **checkable** rather than arguable, and a test now enforces it | `ENGINE_1_INPUT_ENGINE_RULES.md` is no longer byte-identical to its 2026-08-05 lock |
| No code is deleted to make a number match — working, mutation-hardened modules stay | "Facility" is a third category the architecture did not previously name, and a cheap one to abuse |
| A tenth module can no longer appear without an explicit, reviewed decision | — |

## What would prove this wrong

**A document-type field appearing in the Document Evidence Object.** That would make cue detection a producer of a fifth part — a fifth sub-engine in all but name — and this amendment would be wrong rather than merely incomplete. Checked: `src/accountant_dad/artifacts/evidence.py` has zero matches for `document_type`, and `ENGINE_1_INPUT_ENGINE_RULES.md` has **zero matches** for `classif` or `document type` anywhere in its 669 lines.

Second falsifier, weaker: a sub-engine that produces none of the four parts. None exists — `cleaner`, `reader`, `parser` and `confidence` each map to exactly one row of the `:403-408` table.
| The MVP's primary input can emit evidence at all. Every text-layer value now crosses the boundary with a source, a stated measurement state, and an uncertainty marker | Two schema slots are no longer "a number, always." Every reader of them must now ask which state they hold |
| `ENGINE_1_INPUT_ENGINE_RULES.md:245` is satisfied **honestly** rather than by dropping the value — the disjunction is met by carrying all three, not by emitting none | `Provenance.confidence` can no longer be fed straight to arithmetic or a comparison. That is the point, and it is enforced by `__bool__` raising, but it is still a cost at every call site |
| The agreement check gets **stricter**: measured-vs-unmeasured is a new refusal that did not exist before | A frozen P2 schema changed. `CONFIDENCE_SPECIFICATION.md` §3.4's *"the schema is frozen P2 work"* is now qualified rather than absolute |
| "Not measured" is representable **once, in one type**, instead of six modules each inventing a convention — the drift `confidence.py:16-24` was written after | `confidence_report.ParsedField.extraction_confidence` is still typed `Confidence` and cannot carry the sentinel, so the Confidence Report's unmeasured entries are assembled in `pipeline.py` rather than by the `confidence` sub-engine. **Named as open item O11 below, not hidden** |

**Not chosen: exempting an unscored field from the agreement check.** It would have made
the artifact silent about exactly the fields whose reliability is least established —
concealed uncertainty, which `ENGINE_1_ARCHITECTURE.md` P-F3 forbids outright.

**Not chosen: a `Decimal` subclass as the sentinel.** It would satisfy every existing type
annotation and pass `isinstance(value, Decimal)` inside the confidence validator — which
means it would carry a numeric value, and the collapse into zero would be back, wearing
the type system's approval.

## What would prove this wrong

**A slot that needs a third measurement state.** If some reading is neither scored nor
honestly unmeasured — say, scored on a scale not yet established to be this one — then a
two-member union is the same under-modelling this amendment is fixing, one level up.
Nothing in `reader`, `parser` or `cleaner` produces such a shape today: every score is a
`Decimal` from one instrument, or `None`. **If one is found, this amendment needs a
successor, not a patch.**

**Or: an unmeasured value reaching a caller that treats it as a number.** That would be
this amendment failing at its actual job. `__bool__` raising is the guard, and the
red-team test below is the check.

## What now guards it

| Guard | Where |
|---|---|
| Every Engine 1 module carries exactly one of the three classifications, or the suite fails | `tests/unit/test_package.py::test_every_engine_1_module_carries_exactly_one_architectural_classification` |
| The sub-engine set is pinned to the four the locked document names — a fifth fails | `tests/unit/test_package.py::test_the_sub_engine_set_is_exactly_the_four_the_locked_specification_names` |
| A tenth module cannot appear without a decision | `tests/unit/test_package.py::test_no_engine_1_module_exists_without_an_architectural_decision` |
| The three categories cannot overlap | `tests/unit/test_package.py::test_the_three_architectural_categories_are_disjoint` |
| `UNMEASURED` has no truth value — `if not confidence:` raises `TypeError` rather than collapsing into a measured zero | `confidence.py` `UnmeasuredType.__bool__`, pinned in `tests/unit/test_confidence.py` |
| `Confidence` still refuses `float`, `int`, `bool`, `str`, `None`, out-of-range and > 4 places — the new type delegates to the **same** validator | `confidence.py` `_a_measurement_or_its_stated_absence`, pinned in `tests/unit/test_confidence.py` |
| Measured against unmeasured is a **refusal**, not a pass | `evidence.py` `_every_reading_is_scored_and_the_scores_agree`, pinned in `tests/unit/test_evidence.py` |
| A field the reader **did** score still carries that exact `Decimal` — a mutant putting `1.0000` on an unscored reading, or `UNMEASURED` on a scored one, goes red | `tests/unit/test_input_engine_pipeline.py`, `tests/unit/test_evidence.py` |
| Six provenance attributes, none optional, still refused when absent | `evidence.py` `Provenance`, `extra="forbid"` — unchanged, pinned in `tests/unit/test_evidence.py` |
| Every detected field still appears in the Confidence Report, unscored ones included | `evidence.py:337-344`, pinned in `tests/integration/test_engine1_end_to_end.py` |

## Open item this creates

| # | Finding | Owner | What unblocks it |
|---|---|---|---|
| **O11** | **`confidence_report.ParsedField.extraction_confidence` is typed `Confidence` and cannot hold `UNMEASURED`**, so `pipeline.py` assembles the unmeasured `FieldConfidence` entries itself and `ConfidenceReport.confidence_scores` now has two producers. Both are guarded structurally — `_each_name_is_scored_once` refuses an overlap, and the agreement check refuses any disagreement with the provenance — so drift fails loudly rather than silently. It is still two producers for one component. | **The owner.** | Widening `ParsedField.extraction_confidence` to `ConfidenceOrUnmeasured` and removing the filter in `pipeline.parsed_fields`, which returns sole ownership of `confidence_scores` to the `confidence` sub-engine. One annotation; no behaviour change beyond who builds the entry. |

## Approval

```
Proposed by : Claude, 2026-08-06
Approved by : The owner, 2026-08-06, by delegated engineering authority
              — "Determine which is correct: the implementation, or the
                 specification. ... Do not leave them inconsistent. The
                 repository must have one source of truth."
Applied     : ✅ ENGINE_1_INPUT_ENGINE_RULES.md §7 — membership test added
              ✅ ENGINE_1_INPUT_ENGINE_RULES.md §10 — checklist line added
              ✅ ENGINE_1_ARCHITECTURE.md G9.5 — revised (draft, not an amendment)
              ✅ tests/unit/test_package.py — four guards added
              ✅ KNOWN_FAILURES.md F-010 — closed
              ⬜ SUB_ENGINE_RESPONSIBILITIES.md — DELIBERATELY UNTOUCHED. Its §1
                 boxed note already states the engine-level-assembly rule, and
                 ENGINE_1_INPUT_ENGINE_RULES.md:10 makes that document the
                 deeper authority for Input Engine specifics. Nothing to change.
Approved by : The owner, 2026-08-06  — option A of three put to them
Applied     : ✅ src/accountant_dad/confidence.py          — new sentinel, new union, new predicate
              ✅ src/accountant_dad/artifacts/evidence.py  — two slots retyped, agreement rule extended
              ✅ src/accountant_dad/engines/input_engine/pipeline.py
              ✅ docs/CONFIDENCE_SPECIFICATION.md §3.4     — amendment named
              ⬜ SYSTEM_INVARIANTS.md INV-11               — DELIBERATELY UNTOUCHED, not weakened
              ⬜ src/accountant_dad/confidence.py `Confidence` — DELIBERATELY UNCHANGED
```

> **Superseded in part by Amendment 7**, which found the successor condition this
> amendment named in its own *"What would prove this wrong"* and acted on it. Amendment 6
> is not reversed: every rule it states still holds, and the type it introduced is now the
> BASE of three rather than a single class. **O11 above is half closed** — the annotation
> is widened; the matching filter in `pipeline.parsed_fields` is not, and remains open.

---

# Amendment 7 — a measurement has four outcomes, not two

| | |
|---|---|
| **Status** | ✅ **APPROVED 2026-08-06** |
| **Affects** | `src/accountant_dad/confidence.py` · `src/accountant_dad/artifacts/evidence.py` · `src/accountant_dad/engines/input_engine/confidence_report.py` · `src/accountant_dad/engines/input_engine/parser.py` · `src/accountant_dad/engines/input_engine/assembly.py` |
| **Does NOT affect** | `SYSTEM_INVARIANTS.md` INV-11 — **six provenance attributes, none optional, unchanged and not weakened** · the `Confidence` type itself — **still `Decimal` only, [0.0000, 1.0000], ≤ 4 places** · every existing caller written as `isinstance(x, UnmeasuredType)`, which keeps answering correctly |
| **Raised** | 2026-08-06, by the owner, on F-019 |

## What changed

**Old rule** — Amendment 6. Two states: a `Confidence`, or the single `UNMEASURED`
sentinel.

**New rule** — four states, each distinct, each inspectable, none collapsible to a number:

```
MEASURED         a Decimal on the agreed scale. An instrument ran and produced a score
NOT_MEASURED     the value was read, is real, travels into the artifact; nothing scored it
NOT_APPLICABLE   there is no reading here for a score to be ABOUT
FAILED           an instrument was asked and could not produce a reading or a score
```

`MeasurementState` names them. `measurement_state(value)` is the one inspector, total over
the union and **hostile to everything else** — a `float`, an `int`, a `str` or `None`
reaching a confidence slot is refused rather than reported as MEASURED.

Every non-measured state carries a **required, non-blank `basis`** saying WHY. This is the
half that turns "which of the three" into an answer somebody can act on:
`ENGINE_1_INPUT_ENGINE_RULES.md:626` already settles the general form — *"Every uncertainty
marker carries a reason. A bare score cannot become a good question downstream."* A bare
absence is worse than a bare score.

## Which doc / section

| File | Change |
|---|---|
| `src/accountant_dad/confidence.py` | **Added** `MeasurementState`, `NotMeasuredType`, `NotApplicableType`, `MeasurementFailedType`, `measurement_state`, `describe_measurement`, a JSON serialiser. `UnmeasuredType` becomes the **abstract base** of the three; `UNMEASURED` is now a `NotMeasuredType` with its reason written at the definition site. `Confidence`, `MIN`, `MAX`, `CONFIDENCE_PLACES` and `_exactly_a_decimal_in_range` are **unchanged**. |
| `src/accountant_dad/artifacts/evidence.py` | `ConfidenceOrUnmeasured` now admits all four. The disagreement message names both STATES and both reasons. No slot changed shape. |
| `src/accountant_dad/engines/input_engine/confidence_report.py` | `ParsedField.extraction_confidence` widened to `ConfidenceOrUnmeasured` (**O11, annotation half**). A capture-fidelity mismatch records `CAPTURE_FIDELITY_ON_MISMATCH` (FAILED) instead of nothing. A missing field records NOT_APPLICABLE instead of nothing. |
| `src/accountant_dad/engines/input_engine/parser.py` | **Added** `map_cells`. Every table cell carrying text becomes a `MappedField` with a unique locator name and its own box, so a cell's provenance is built by the same code path a text region's is. |
| `src/accountant_dad/engines/input_engine/assembly.py` | Docstring only. The confidence-authority tension it reported is resolved and now says so. |

## Why

**The root cause was never the missing sentinel. It was that the architecture modelled the
RESULT of measuring and never the ACT of it.**

`confidence.py` defined the score. Everything else — did an instrument run? did it
succeed? was scoring even a meaningful question here? — was carried by `None`. And `None`
was already spoken for four ways in the same pipeline:

```
reader.TextRegion.extraction_confidence   no recogniser ran
confidence_report.RegionReading.text      the region could not be read
parser.Cell.text                          no text was reported at this grid position
DocumentEvidenceObject.human_business_context   no note was supplied
```

So the absence of a measurement **had no name**, and a fact with no name cannot be
carried, checked or refused. When a schema demands a number from a world that supplies one
only sometimes, code has exactly three moves: **INVENT a number, DROP the value, or
CRASH.** This repository has done the first two, in production paths, and each fix named
one more special case rather than the class.

**The transform (Law 53):** stop modelling the score, model what happened when we tried to
measure. "Measured" becomes one of four outcomes rather than the only representable one,
and the other three stop having to disguise themselves as numbers or as silence.

**Why one base and not three siblings.** Every caller already written as
`isinstance(x, UnmeasuredType)` keeps getting the right answer to *"is a measurement
absent here?"* as states are added (Law 33). Sibling classes with no shared base would have
made those call sites report a non-measured value as **measured** — silently, and in the
reassuring direction, which is the failure mode this whole module exists to prevent
(Law 11).

## What failure forced it

**F-019, and the fact that Amendment 6 predicted its own successor.** That amendment's
*"What would prove this wrong"* section reads: *"A slot that needs a third measurement
state ... If one is found, this amendment needs a successor, not a patch."*

Two were found, both on real values in real paths:

| State | The value that needed it |
|---|---|
| NOT_APPLICABLE | a field the document does not contain, and a grid position it left blank. There is no reading for a score to be about, and filing that under "nobody scored it" invents work on empty cells while hiding genuinely unscored values among them |
| FAILED | a capture-fidelity comparison that ran and could not produce a score, because `cleaner` and `reader` had both broken the pass-through guarantee they are contractually held to. Filing a broken guarantee under the same heading as an ordinary unscored text-layer reading is the collapse the states exist to prevent |

## The agreement rule is extended again, never exempted

```
same state, both measured, equal numbers   AGREE
same state, both measured, different       DISAGREE
same non-measured state                    AGREE
different states                           DISAGREE   — including every measured-against-
                                                        absent pair AND every pair of two
                                                        DIFFERENT absences (NEW)
```

NOT_MEASURED against NOT_APPLICABLE is a **new refusal**: one side says a real value is
carried with nothing behind it, the other says there is no value at all. Two components
that disagree about whether the document was even read there have not "both declined to
score."

**The `basis` is deliberately NOT part of agreement.** Two components may say "nothing
scored this" in different words and still state the same fact. Comparing explanations would
turn a prose edit into a refused artifact.

## The trade-off

| Gained | Lost |
|---|---|
| Three genuinely different facts stop wearing one shape, and the agreement check gains two new ways to fail | Four states is more to hold in mind than two. Every reader of a confidence slot now asks `measurement_state(x)` rather than one `isinstance` |
| Every absence states WHY, so the artifact answers *why* and not only *whether* | `basis` is free text. Nothing checks that it is a GOOD reason, only that it exists |
| A stated absence can be written to JSON at all — a latent defect that pre-dated this amendment and made any artifact carrying one undumpable | JSON now carries a heterogeneous shape in one slot: a string for a score, an object for an absence. A reader must branch |
| Table cell values reach the artifact with a name, a location and a state, through the same code path text regions already use | `parser.mapped_fields` now holds two kinds of mapping. They are the same KIND of fact — a named value with a source reference — but the collection is no longer "one per reader region" |
| Two silent gaps closed in the Confidence Report: a capture-fidelity mismatch and a missing field each now state their reliability instead of being omitted | A document with missing fields or a mismatched note produces a longer report. Nothing that was there is removed |

**Not chosen: an enum field on one class.** A single class with a `state` attribute would
make `isinstance` useless for the question every existing call site asks, and would let a
value be constructed in no state at all.

**Not chosen: reusing `measurement.AbsentType`.** Amendment 6 settled this and the
reasoning is unchanged — different fact, and a circular import.

**Not chosen: giving `parser` the four states.** `parser` may not import
`accountant_dad.confidence` — a pinned test refuses it — and that is correct:
`ENGINE_1_INPUT_ENGINE_RULES.md:109` says `parser` emits SIGNALS and only `confidence`
turns a signal into a state. `parser.MappedField.extraction_confidence` therefore stays
`reader`'s raw `Decimal | None`, and `pipeline._recorded_confidence` remains the single
place that decides what an absent signal means.

## What would prove this wrong

**A value whose measurement outcome is none of the four.** The obvious candidate is
"scored, but on a scale not yet established to be this one" — a raw detector number before
calibration. Today that is kept out of the artifact entirely and lives in
`measurement.NamedSignal` as a plain `float`, deliberately. If it ever needs to reach a
`Provenance`, this amendment needs a successor rather than a patch.

**Or: a caller that branches on `isinstance(x, UnmeasuredType)` and MEANS "not measured
specifically".** That call site would silently treat NOT_APPLICABLE and FAILED as
NOT_MEASURED. Two exist today and are recorded as open item O12 below; neither can reach a
non-NOT_MEASURED value on any current path, because `pipeline` produces only `UNMEASURED`.

**Or: an absence reaching a caller that treats it as a number.** `__bool__`, `__lt__`,
`__le__`, `__gt__` and `__ge__` all raise, and `measurement_state` refuses a `float`
outright. Pinned in `tests/unit/test_confidence.py`.

## What now guards it

| Guard | Where |
|---|---|
| All **sixteen** state pairings agree exactly when the states match — generated, not listed | `tests/unit/test_confidence.py::test_every_pairing_of_states_agrees_exactly_when_the_states_match` |
| A **fifth** member added to `MeasurementState` and not added to the matrix turns the suite red | `tests/unit/test_confidence.py::test_the_matrix_covers_every_state_the_enum_declares` |
| The base cannot be instantiated — "an absence, unspecified" is unrepresentable | `tests/unit/test_confidence.py::test_the_base_state_cannot_be_constructed_and_says_why` |
| No absence can be built without a non-blank reason, and a padded blank is a blank | `tests/unit/test_confidence.py::test_no_absence_may_be_constructed_without_a_stated_reason` |
| No absence has a truth value, an ordering, a numeric conversion, or a `Decimal` in its ancestry | `tests/unit/test_confidence.py`, four tests, all three states parametrised |
| Nothing that merely LOOKS like a score is reported as measured — `1.0`, `True`, `"0.98"`, `None`, `ABSENT` all refused | `tests/unit/test_confidence.py::test_nothing_that_merely_looks_like_a_score_is_reported_as_measured` |
| Every state survives a JSON dump, and an absence is never written as a number or `null` | `tests/unit/test_confidence.py`, four serialisation tests |
| Two DIFFERENT absences are refused by the real artifact, in both directions | `tests/unit/test_evidence.py::test_two_different_absences_are_a_disagreement_the_artifact_refuses` |
| No confidence slot in the schema carries a default | `tests/unit/test_evidence.py::test_no_confidence_bearing_slot_in_this_schema_carries_a_default` |
| **No module may write a literal into a `Provenance` or `FieldConfidence` confidence slot** — AST over authored source, with a second test proving the matcher would catch one | `tests/unit/test_evidence.py::test_no_module_writes_a_literal_into_a_confidence_slot` |
| Every confidence in a real assembled artifact yields a state, and every non-measured one carries a reason | `tests/unit/test_evidence.py::test_every_confidence_in_a_real_artifact_names_its_state_and_its_reason` |
| Every mapped cell carries a unique name and its own box; a blank grid position is not mapped and is not lost | `tests/unit/test_input_engine_parser.py`, nine `map_cells` tests |
| A capture-fidelity mismatch records FAILED rather than silence; a document with no note gains no entry | `tests/unit/test_input_engine_confidence.py`, two tests |

## Open items this creates

| # | Finding | Owner | What unblocks it |
|---|---|---|---|
| **O11** *(carried, half closed)* | `ParsedField.extraction_confidence` is now `ConfidenceOrUnmeasured`. The matching filter in `pipeline.parsed_fields` still excludes unscored mappings, so `ConfidenceReport.confidence_scores` still has two producers. | The `pipeline.py` workstream. | Removing `if field.extraction_confidence is not None` from `pipeline.parsed_fields`, and the now-redundant `unmeasured_field_scores`. |
| **O12** | **Two call sites ask `isinstance(x, UnmeasuredType)` and mean "not measured specifically"** — `pipeline.unmeasured_field_scores` and `tests/integration/test_engine1_end_to_end.py`, which classifies anything failing that test as *measured*. Neither can be reached by a non-NOT_MEASURED value today, because `pipeline` produces only `UNMEASURED`. | The `pipeline.py` workstream. | Replacing both with `measurement_state(x)`. |
| **O13** | **NOT_APPLICABLE and FAILED have limited live producers.** FAILED fires today only on a capture-fidelity mismatch; NOT_APPLICABLE fires only when `parser` is given an expected-field list, and it is given none. **Stated rather than manufactured** — inventing a producer to make the state look exercised is the fabrication these types exist to refuse. | — | `reader` reporting a per-region recognition failure as a STATE rather than raising for the whole reading, and `parser` receiving an expected-field list. |
| **O14** | **A cell's per-cell provenance reaches the artifact through `detected_fields`, not through `DetectedTable`**, which carries one `Provenance` per table. That is a limit of the frozen schema, not a choice. | **The owner.** | A schema change giving `DetectedTable` per-cell provenance — or a decision that the `detected_fields` route is the intended one, in which case this is closed as designed. |

## Approval

```
Proposed by : Claude, 2026-08-06
Approved by : The owner, 2026-08-06 — F-019, verbatim:
              "Introduce an explicit 'measurement unavailable' state. Do NOT
               use 1.0, 0.0, fake confidence, or placeholder confidence.
               Confidence must distinguish between: measured, not measured,
               not applicable, failed. Propagate this state throughout
               Engine 1. Apply the same architecture to table extraction and
               every extracted value."
Applied     : ✅ src/accountant_dad/confidence.py
              ✅ src/accountant_dad/artifacts/evidence.py
              ✅ src/accountant_dad/engines/input_engine/confidence_report.py
              ✅ src/accountant_dad/engines/input_engine/parser.py
              ✅ src/accountant_dad/engines/input_engine/assembly.py
              ✅ tests — confidence, evidence, parser, confidence_report, redteam
              ⬜ SYSTEM_INVARIANTS.md INV-11        — DELIBERATELY UNTOUCHED, not weakened
              ⬜ src/accountant_dad/confidence.py `Confidence` — DELIBERATELY UNCHANGED
              ⬜ src/accountant_dad/engines/input_engine/pipeline.py — NOT OWNED by this
                 change; O11 and O12 record exactly what it needs
```

---

# Amendment 8 — Decision A7 is authoritative: confidence gates NOTHING

| | |
|---|---|
| **Status** | ✅ **APPROVED 2026-08-06** |
| **Affects** | `docs/ADVERSARIAL_TESTING.md` · `docs/EXECUTION_QUEUE.md` · `docs/TECHNOLOGY_STACK.md` · `docs/ACCOUNTING_DEFINITIONS.md` · `docs/APPLICATION_LAYER.md` |
| **Does NOT affect** | the separation gate itself (`MEASUREMENT_FRAMEWORK.md` §10 — a gate on whether confidence may be USED, not a confidence gate) · build acceptance thresholds such as *margin ≥ 0.30* · the propagation BOUND `Understanding Confidence ≤ Evidence Reliability`, which constrains a value and routes nothing |
| **Raised** | F-004, open since 2026-08-05 |

## What changed

**Old rule** — five locked or live documents specified behaviour triggered by a confidence
value crossing a threshold.

**New rule** — **no document specifies confidence gating.** Every one of the five states
the same outcome through a mechanism that needs no number, and each says so in place.

| Document | Old | New |
|---|---|---|
| `ADVERSARIAL_TESTING.md` attack 8 | *"Low confidence → **Clarification**"* | *"Unread regions → **missing information** → **Clarification**"* |
| `EXECUTION_QUEUE.md` | *"**Insufficient confidence** produces `I don't know` or a Clarification Request"* | **Applied by SUPERSESSION, not by revision** — the same replacement wording, stated in a block directly beneath the clause, which is left byte-identical. See "The one that could not be edited in place" below |
| `TECHNOLOGY_STACK.md` stack table | Gemini Vision *"**fallback only**, when OCR confidence is below threshold"* | *"**fallback only** — and it has **no trigger**"* |
| `TECHNOLOGY_STACK.md` blockers | *"OCR confidence threshold \| **a number nobody has set**"* | *"Gemini fallback trigger \| **undecided** — a routing decision, not a number"* |
| `ACCOUNTING_DEFINITIONS.md` §6 Uncertainty | *"the set of open doubts, **plus any confidence below the threshold at which the system may act unattended**"* | *"the set of open doubts."* The second term is **struck** |
| `APPLICATION_LAYER.md` failure classes | *"**Confidence below threshold** \| Engine 3/4"* | *"**Unresolved doubt or unestablished fact** \| Engine 3/4"* |

**Two of these were not on F-004's list.** F-004 named three documents;
`ACCOUNTING_DEFINITIONS.md` and `APPLICATION_LAYER.md` were found by sweeping every
markdown file in the repository for gating language rather than by trusting the list. The
inventory the sweep produced is in the commit that carries this amendment.

### The one that could not be edited in place

`EXECUTION_QUEUE.md`'s clause is cited by a **content digest** —
`conformance_registry.py:2119` holds
`docs/EXECUTION_QUEUE.md#an-incorrect-entry-must@b50bd021b31e`, and the digest covers the
LINE. Editing the words breaks the citation, and `conformance_registry.py` belongs to
another workstream. **Discovered by the suite going red, not by reading**, which is the
system working: a content-addressed citation is supposed to notice exactly this.

So the amendment is applied there by **supersession**: the clause line is byte-identical,
and a block directly beneath it states what the sentence must be read as, and why the
words themselves still stand. **The two changes must land together**, and the exact pair
is:

```
docs/EXECUTION_QUEUE.md  lines 130-131 — the clause under "So the floor is set on
                                          autonomy", currently two lines
  KEEP    the opening sentence, verbatim, up to and including "silently accepted."
  REPLACE everything after it — the "Insufficient confidence produces ..." half —
          with the wording quoted in the block beneath the clause in that file,
          beginning "a fact the system could not establish"
  DELETE  the superseding block, which exists only because the edit is blocked

src/accountant_dad/conformance_registry.py  line 2119
  before  "docs/EXECUTION_QUEUE.md#an-incorrect-entry-must@b50bd021b31e",
  after   the same citation with the digest recomputed over the new line
```

> **The clause is described here rather than quoted.** The conformance scanner treats any
> line in `docs/**` carrying its marker phrase as a NEW prohibition clause needing its own
> rule or exclusion — so pasting the sentence into this file would manufacture two
> prohibitions that no artifact can witness. Measured, not assumed: it did, and the suite
> said so. The replacement wording is quoted in `EXECUTION_QUEUE.md` itself, beneath the
> clause it replaces, which is where a reader needs it anyway.

**This is the weakest of the five in precedence and the loudest about it.**
`EXECUTION_QUEUE.md:3` declares *"Precedence: none. This document has no authority."*
A reader who lands on the clause now finds the correction attached to it.

## Why

**Decision A7 is binding and the documents outranked nothing.** `MEASUREMENT_FRAMEWORK.md`
§10 states it outright: until

```
accuracy(top confidence tercile) − accuracy(bottom tercile)  ≥  0.30
```

is measured and passes, **confidence is an ordinal ranking, not a probability, and it may
gate NOTHING.** Every one of Engine 1's sixteen parameters is `UNSET` by design.

`ADVERSARIAL_TESTING.md` sits at the **same precedence level** as the rule forbidding it,
so precedence alone never settled it. That is why this had to be an amendment and not a
correction.

## What failure forced it

**Nothing has failed yet, and that is the point at which this is cheapest to fix.** The
failure it prevents is precise: *whoever implements one of these next builds a threshold,
believing a locked document told them to* — and then has to invent the number, because none
exists. That is Law 52 and Law 54 broken at the same keystroke, with a locked document as
the defence.

The near miss is on the record. `TECHNOLOGY_STACK.md` recorded the Gemini trigger as
*"UNKNOWN — REQUIRES A NUMBER FROM THE OWNER"*, which frames the blocker as a **missing
number**. Supplying it would not have unblocked anything: A7 forbids the mechanism, so the
number would have been forbidden the moment it arrived.

## The trade-off

| Gained | Lost |
|---|---|
| No locked document instructs anyone to build a confidence gate | Five documents are no longer byte-identical to their lock |
| Attack 8, the Clarification path and the Uncertainty definition all work **today**, with no calibration and no number | Attack 8's mechanism is now specific to how `reader` reports unread regions, so it is coupled to Engine 1's shape in a way *"low confidence"* was not |
| The Gemini fallback blocker is stated honestly: the trigger is **undecided**, not merely unset | The fallback is further from implementable than the old wording implied — an honest loss of apparent progress |
| `Uncertainty` becomes measurable as written: `count(open doubts)`, with nothing undefined in it | The definition is narrower than the owner originally wrote. **Nothing measurable is lost** — the same document's next sentence already said the second term was undefined — but a term the owner wrote is gone, and restoring it needs them |

**Not chosen: deleting attack 8, the Clarification row, or the fallback.** §E.8 — adding
rigour is in scope, subtracting what the owner specified is not. Every purpose survives;
only the stated mechanism changed.

**Not chosen: leaving the wording and adding a footnote.** A document that says one thing
and footnotes the opposite is exactly the state F-004 describes, with a warning attached.

## What now guards it

| Guard | Where |
|---|---|
| Every revised line says *"Revised by Amendment 8"* in place, so a reader who lands on it without reading this file still learns the rule | the five documents |
| The separation gate itself is untouched and still the only thing that could ever unblock confidence gating | `MEASUREMENT_FRAMEWORK.md` §10 |
| Engine 1 asserts in code that it compares no confidence against any number | `docs/ENGINE_1_CONFIDENCE_PARAMETERS.md` — no numeric literal used as a threshold anywhere in `engines/input_engine/`, two tests |
| A confidence written as a literal into an artifact slot fails the suite | `tests/unit/test_evidence.py::test_no_module_writes_a_literal_into_a_confidence_slot` |
| No absence has an ordering, so `confidence < threshold` against one is a `TypeError` rather than a branch | `confidence.py` — `__lt__`/`__le__`/`__gt__`/`__ge__` refuse, pinned in `tests/unit/test_confidence.py` |

## What would prove this wrong

**A sixth document specifying confidence gating that the sweep missed.** The sweep matched
eight regular-expression patterns over every `.md` file in `docs/` and the repository root.
It cannot catch gating described without any of those words — *"when the reading is weak,
route to review"* would pass it. **A future reader finding one should treat this amendment
as incomplete rather than as wrong**, and revise the document the same way.

**Or: the separation test passing, and a threshold then being correct after all.** That
does not reverse this amendment. It unblocks a NEW one, per `MEASUREMENT_FRAMEWORK.md`, and
the number would still have to come from the owner.

## Approval

```
Proposed by : Claude, 2026-08-06
Approved by : The owner, 2026-08-06 — F-004, verbatim:
              "Decision A7 is authoritative. Update every conflicting
               document. Remove all threshold-based confidence gating
               language. Standardise the repository around measurement-first
               architecture."
Applied     : ✅ docs/ADVERSARIAL_TESTING.md      — attack 8 + a paragraph naming the change
              🔄 docs/EXECUTION_QUEUE.md          — by SUPERSESSION. The clause line is
                 byte-identical because conformance_registry.py:2119 cites it by content
                 digest and that file is another workstream's. Exact paired change above
              ✅ docs/TECHNOLOGY_STACK.md         — stack row, blocker row, the note
              ✅ docs/ACCOUNTING_DEFINITIONS.md   — §6 Uncertainty, second term struck
              ✅ docs/APPLICATION_LAYER.md        — failure class renamed
              ✅ docs/CONFIDENCE_SPECIFICATION.md — open items O6 and O10 closed
              ✅ KNOWN_FAILURES.md F-004          — closed
              ⬜ MEASUREMENT_FRAMEWORK.md §10     — DELIBERATELY UNTOUCHED. It is the rule
                 the other five now obey, not a document that needed changing
```
