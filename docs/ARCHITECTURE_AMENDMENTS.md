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

## The trade-off

| Gained | Lost |
|---|---|
| The count becomes **checkable** rather than arguable, and a test now enforces it | `ENGINE_1_INPUT_ENGINE_RULES.md` is no longer byte-identical to its 2026-08-05 lock |
| No code is deleted to make a number match — working, mutation-hardened modules stay | "Facility" is a third category the architecture did not previously name, and a cheap one to abuse |
| A tenth module can no longer appear without an explicit, reviewed decision | — |

## What would prove this wrong

**A document-type field appearing in the Document Evidence Object.** That would make cue detection a producer of a fifth part — a fifth sub-engine in all but name — and this amendment would be wrong rather than merely incomplete. Checked: `src/accountant_dad/artifacts/evidence.py` has zero matches for `document_type`, and `ENGINE_1_INPUT_ENGINE_RULES.md` has **zero matches** for `classif` or `document type` anywhere in its 669 lines.

Second falsifier, weaker: a sub-engine that produces none of the four parts. None exists — `cleaner`, `reader`, `parser` and `confidence` each map to exactly one row of the `:403-408` table.

## What now guards it

| Guard | Where |
|---|---|
| Every Engine 1 module carries exactly one of the three classifications, or the suite fails | `tests/unit/test_package.py::test_every_engine_1_module_carries_exactly_one_architectural_classification` |
| The sub-engine set is pinned to the four the locked document names — a fifth fails | `tests/unit/test_package.py::test_the_sub_engine_set_is_exactly_the_four_the_locked_specification_names` |
| A tenth module cannot appear without a decision | `tests/unit/test_package.py::test_no_engine_1_module_exists_without_an_architectural_decision` |
| The three categories cannot overlap | `tests/unit/test_package.py::test_the_three_architectural_categories_are_disjoint` |

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
```
