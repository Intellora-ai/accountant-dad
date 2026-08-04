# Architecture Audit

> Run against the Application Layer design, 2026-08-03.
> **17 points. Every result is a check that was actually run, not an assertion.**

---

## Verdict

> ## ⚠️ NOT FROZEN — 1 unresolved issue
>
> The sentence **"Architecture Frozen — Ready for Engine Implementation."** is **withheld.**
>
> **16 of 17 points pass.** One blocks the freeze, and it needs a decision from you rather than more design work.
>
> **Changed 2026-08-03:** Issue 1 (`Human Instruction` artifact ownership) is **CLOSED** by Amendment 4 — the artifact is withdrawn, INV-4 is untouched, and points 6 and 12's artifact clause now pass.

---

## All components

| Component | Location | Owns | Never owns |
|---|---|---|---|
| **Application Layer** | `src/services/` | Transaction ID creation · starting engines · routing artifacts · lifecycle · retrying engine execution · state transitions · deciding completion | Any decision · artifact · confidence · reasoning · authority-table row |
| **Knowledge Brain** | `src/brain/` | Accounting standards · GST · Income Tax · Companies Act · ICAI guidance · chart of accounts · policies · historical patterns | Decisions · artifacts · confidence · **workflow** · routing · state · retry |
| **Engine 1 — Input** | `src/engines/input/` | Document Evidence Object · provenance | Orchestration · downstream reasoning |
| **Engine 2 — Understanding** | `src/engines/understanding/` | Business Understanding Object · multi-document aggregation | Orchestration · accounting decisions |
| **Engine 3 — Accounting** | `src/engines/accounting/` | Accounting Decision · doubts · Accounting Risk Analysis | Orchestration · validation · execution |
| **Engine 4 — Clarification** | `src/engines/clarification/` | Clarification Request · Clarification Status · which doubts block | Answering · deciding · workflow state |
| **Engine 5 — Validation** | `src/engines/validation/` | Validation Decision · Risk Assessment · four statuses | Fixing a defect · holding a workflow gate |
| **Engine 6 — Execution** | `src/engines/execution/` | Execution Result · voucher translation · re-posting · idempotency | Reasoning · restarting workflows · backward arrows |

---

## The 17 points

### ✅ 1 — No contradictions with any locked document

```
git diff --numstat  over all 23 locked files  →  0 changed files
```

**No locked document was modified.** The one architecture change (`WaitingForApproval`) exists **only** as a proposal in `ARCHITECTURE_AMENDMENTS.md`, and every document referencing it is marked ⚠️ PROPOSED — verified file by file.

### ✅ 2 — Every responsibility belongs to exactly one component

`APPLICATION_LAYER_RESPONSIBILITY_MATRIX.md` lists every responsibility with one owner. The four historic collisions are explicitly re-split: retry · error routing · risk · state-versus-status.

### ✅ 3 — No duplicated responsibilities

Zero responsibilities with two owners. Zero with none.

### ✅ 4 — No circular dependencies

```
Human → Application Layer → each engine → back to Application Layer
Engines → Brain (one-directional, dotted)
Application Layer ⇄ Brain :  NO ARROW
Engine ⇄ Engine           :  NO ARROW
```

Depth 2, no cycle. AL-INV-5 forbids engine-to-engine calls, which is the only way a cycle could form.

### ✅ 5 — Every engine has a defined input/output contract

Six boundaries in `APPLICATION_LAYER_CONTRACTS.md`, each with input artifact · output artifact · guarantees · preconditions · postconditions · failure conditions · what the Application Layer must not do.

### ✅ 6 — Every artifact has exactly one owner

Six canonical artifacts, six owners, Application Layer owns none.

**Was an issue, now closed.** `FORWARD_DEPENDENCY_INVENTORY.md:94` proposed a **Human Instruction** artifact *"owned by the Application Layer"* against INV-4's *"never owns … any artifact."* **Amendment 4 withdrew the artifact** — it held zero of the four properties of an artifact here, and *"post this tomorrow"* is orchestration state INV-4 already grants the Application Layer. **Six remains six. INV-4 untouched.**

### ✅ 7 — Every state transition is defined

Nine states. Each has entry condition, exit condition, allowed transitions and **forbidden** transitions, in `APPLICATION_LAYER.md` §5.

### ✅ 8 — Every failure path is handled

`APPLICATION_LAYER_FAILURE_MATRIX.md` — 12 business failures, 8 runtime failures, each with detection, owner, retryability and escalation. The business/runtime split follows one test: *did the engine reach a conclusion?*

### ✅ 9 — Every retry path is defined

Retryable: timeout · crash · unexpected exception. Non-retryable: every business failure · schema violation · **Engine 6 always**. Restart point is always the last completed artifact.

### ✅ 10 — Every extension point is documented

New engine · new validator · new reasoning module · new output destination. Each with what must **not** happen. The rule: *if a change requires the Application Layer to understand what an artifact means, it is being extended in the wrong place.*

### ✅ 11 — Every configuration point is documented

Six required keys, **all with no default**. A missing value refuses startup and names the key.

### ⚠️ 12 — Every invariant is preserved — **1 ISSUE**

14 Application Layer invariants, each mapped to the system invariant it upholds. None contradicts, weakens or reinterprets a system invariant.

**But** AL-INV-9 depends on Amendment 2, which is **not approved**. Until then the design describes a state the locked architecture does not contain. **Unresolved — see Issue 2.**

### ✅ 13 — Sequence diagrams match the architecture

Five diagrams — happy path · clarification loop · approved-with-warning hold · engine crash · correction. Every arrow passes through the Application Layer. **No engine-to-engine arrow exists in any diagram.**

### ✅ 14 — Component diagram matches the sequence diagrams

Every arrow in every sequence diagram exists in the component diagram. Brain arrows are dotted and one-directional. **No arrow between Application Layer and Brain**, in either.

### ✅ 15 — Nothing in the Brain violates its locked definition

```
grep for  Brain ... (orchestrates|routes|sequences|retries|decides)
excluding prohibitions  →  0 hits
```

Every mention of the Brain in every new document is either a knowledge statement or an explicit prohibition. The Brain gains no workflow, state, routing, retry or decision.

### ✅ 16 — The Application Layer is the ONLY orchestration component

No engine orchestrates. The Brain does not orchestrate. No second orchestrator exists. `ENGINE_1..3` already state *"Orchestrate the entire system"* is outside every engine.

### ✅ 17 — No TODOs, placeholders, assumptions or undefined behaviour

```
grep -icE 'TODO|TBD|FIXME'  across all 7 new documents  →  0
```

Every state has defined entry, exit and forbidden transitions. Every failure has an owner. Every configuration key is named. **No number was chosen by me** — retry limits and timeouts are required config with no default.

---

## Unresolved issues

### ✅ Issue 1 — `Human Instruction` artifact ownership — **CLOSED 2026-08-03**

| | |
|---|---|
| **Was** | `FORWARD_DEPENDENCY_INVENTORY.md:94` proposed an artifact **owned by the Application Layer**. INV-4: the Application Layer **"never owns … any artifact."** |
| **Resolved by** | **Amendment 4** — the artifact is **withdrawn.** Neither a seventh artifact nor a change to INV-4 was needed |
| **The defect** | The assumption *"an instruction has to be an artifact."* It held **zero of four** artifact properties — not immutable, not versioned, consumed by no engine, not in the accounting audit trail |
| **Where it actually lives** | INV-4's own left column already grants the Application Layer *"lifecycle · coordinating state transitions."* *"Post this tomorrow"* is **when a transition fires** — a field on orchestration state, not an artifact |
| **Classification deleted too** | The split is made **at input** — a business-context box and a scheduling control. The Application Layer never infers which is which, because inference would be reasoning, which INV-4 also forbids |
| **Cost** | Zero locked documents changed. INV-4 stands exactly as written |

**Falsifier on record:** an instruction genuinely needing immutability and an audit trail would kill this. The closest candidate — *"the client authorized posting to a closed period"* — is **evidence of an authorization**, and already has two homes with correct owners.

### Issue 2 — `WaitingForApproval` amendment not approved

| | |
|---|---|
| **Conflict** | The design uses `WaitingForApproval`. The locked state machine does not contain it |
| **Status** | **Proposed** in `ARCHITECTURE_AMENDMENTS.md`, awaiting your approval |
| **Blocks** | Audit point 12 |
| **Resolution needs** | One decision: approve the state, or remove `Approved With Warning` from the architecture |
| **If rejected** | AL-INV-9 is void, `release_waiting_for_approval()` is deleted, and `ENGINE_5:439` loses `risk_assessment`'s only output path |

Every document referencing this state is marked ⚠️ PROPOSED, so nothing silently assumes approval.

---

## What has to happen before this says "Frozen"

```
1  Resolve Human Instruction artifact ownership     ✅ DONE — Amendment 4, 2026-08-03
2  Approve or reject the WaitingForApproval state   ⬜ OPEN — Issue 2
```

**One decision remains. No design work, and no further documents are needed.**

---

## Assumptions made

Recorded so none is invisible.

| # | Assumption | Basis | If wrong |
|---|---|---|---|
| 1 | Brain interface belongs in P2 | *"Brain never returns a decision"* is a pure predicate; P2 is predicates without AI | Interface moves to P3; engines then call an undefined interface at P3, which is a forward dependency |
| 2 | Application Layer belongs in P3 | P3 is defined as proving the pipeline; a pipeline is orchestration | Nothing could be sequenced at P3, so P3 could not exist as defined |
| 3 | Reading a Validation status to pick a transition is workflow, not reasoning | It is a lookup — *"this status means state X"* — never a judgement about soundness | The Application Layer could not route at all, and INV-4's *"routing artifacts"* would be unimplementable |
| 4 | A crashed Engine 6 is restarted by `resume_transaction()`, not `retry_engine()` | `retry_engine()` on Engine 6 would be a re-post, which is `posting_manager`'s | A crashed Engine 6 would be unrecoverable |
| 5 | Human business context stays evidence, passed to Engine 1 | Locked at `6416be4` inside the Document Evidence Object | ✅ **Confirmed by Amendment 4** — no longer an assumption |

---

## Verification commands

Re-runnable. Every claim above came from one of these.

```bash
# 1  no locked document modified
git diff --numstat docs/SYSTEM_INVARIANTS.md docs/DATA_FLOW.md \
  docs/SYSTEM_BOUNDARIES.md docs/MVP_ARCHITECTURE.md docs/ENGINE_*.md \
  docs/COMMUNICATION_RULES_*.md | wc -l          # → 0

# 2  six phases byte-identical
sed -n '/^P1 /,/^P6 /p' docs/MVP_IMPLEMENTATION_BLUEPRINT.md

# 3  no TODOs
grep -icE 'TODO|TBD|FIXME' docs/APPLICATION_LAYER*.md \
  docs/ARCHITECTURE_AMENDMENTS.md                # → 0

# 4  Brain never given workflow
grep -inE 'Brain [^.|]{0,40}(orchestrat|routes|sequences|retries|decides)' \
  docs/APPLICATION_LAYER*.md | grep -viE 'never|not|no|cannot|must'   # → 0

# 5  WaitingForApproval always marked proposed
for f in docs/APPLICATION_LAYER*.md docs/ARCHITECTURE_AMENDMENTS.md; do
  grep -q 'WaitingForApproval' "$f" && \
    { grep -qE 'PROPOSED|Amendment 2' "$f" || echo "UNMARKED: $f"; }
done                                             # → no output

# 6  six artifacts, Application Layer owns none
grep -c 'Route only' docs/APPLICATION_LAYER_RESPONSIBILITY_MATRIX.md  # → 6
```

---

## Statement

**"Architecture Frozen — Ready for Engine Implementation."**

⛔ **NOT STATED.** Two unresolved issues remain, both listed above, both requiring a decision from you.

No engine implementation may begin until this section states that sentence without qualification.
