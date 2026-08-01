# Engine 4 — Clarification Engine: Specification Lock

> **Status: LOCKED.** This is the permanent engineering specification for the Clarification Engine.
>
> **Specification only — no implementation.** No code, no Python files, no databases, no APIs, no AI implementation, no user interface, no external integrations.
>
> **Precedence.** [`SUB_ENGINE_RESPONSIBILITIES.md`](SUB_ENGINE_RESPONSIBILITIES.md) remains canonical for the system-wide map. **This document is the deeper authority for Clarification Engine specifics.** Where they overlap they must agree; a disagreement is a defect to be fixed, not a choice to be made.

---

# 1. Engine Identity

## Engine Name

**Clarification Engine**

## Core Role

The Clarification Engine is the **uncertainty resolution layer** of the AI Accountant.

> Detect what prevents a decision from being safely completed, and emit a structured request for what is required — without ever resolving it.

### The question it answers

> **"What information is missing, uncertain, conflicting, or unsupported, and what clarification is required before this decision can safely continue?"**

### The questions it does not answer

| Question | Owner |
|---|---|
| ~~What information exists?~~ | Engine 1 — Input |
| ~~What happened in the business?~~ | Engine 2 — Understanding |
| ~~How should it be accounted?~~ | Engine 3 — Accounting |
| ~~Is the decision approved?~~ | Engine 5 — Validation |

### Why this engine exists

**A reliable system must know when it does not know.**

The engine does not remove uncertainty by guessing. It removes uncertainty by causing better information to be obtained — and it never obtains that information itself.

---

# 2. Mission

**Prevent incorrect execution by detecting uncertainty before validation.**

> **Validation should never discover uncertainty that Clarification should have identified.**

## Success

- Every decision-blocking uncertainty is identified.
- Only necessary clarification is asked for.
- Uncertainty is preserved.
- No hidden assumptions survive.
- Confidence improves without any fact being invented.

## Failure

- Missed uncertainty.
- Unnecessary clarification.
- Hidden assumptions.
- Silent conflict resolution.
- Unsupported certainty.

---

# 3. Responsibility

## The Clarification Engine owns

- Missing information detection.
- Uncertainty detection.
- Conflict identification.
- Clarification generation.
- Clarification prioritisation.
- Clarification traceability.
- Clarification lifecycle tracking.
- Clarification confidence.
- Clarification completeness.

## The Clarification Engine does NOT own

- Document extraction.
- Business understanding.
- Accounting reasoning.
- Validation approval.
- Posting or execution.
- Modification of the Document Evidence Object, Business Understanding Object or Accounting Decision.

---

# 3A. Decision Authority

> **The Clarification Engine controls only clarification decisions.**
>
> **No engine outside the Clarification Engine can modify its decisions.**

| Component | Can decide | Cannot decide |
|---|---|---|
| **`missing_information`** | What required information is missing | How missing information should be interpreted |
| **`uncertainty_detection`** | Whether uncertainty exists | Whether uncertainty is acceptable |
| **`understanding`** | Whether outputs conflict | Which answer is correct |
| **`stop_decision`** | Whether clarification is required at all | Whether accounting changes |
| **`answer_understanding`** | Which clarification should be resolved first | Whether accounting changes |
| **`question_generator`** | Final clarification structure | Accounting conclusions |
| **`decision_updater`** | Clarification status | Whether accounting decisions become valid |
| **Clarification Engine parent** | **Final Clarification Request assembly** | Accounting treatment |

## Global rules

- No sub-engine overrides another.
- No sub-engine removes uncertainty.
- No sub-engine invents information.
- No sub-engine changes upstream artifacts.
- **The parent engine assembles; it does not rewrite sub-engine outputs.**

---

# 4. Input Contract

## Primary input

```text
Accounting Decision          ← created by decision_output, owned by the Accounting Engine
```

Carries accounting treatment · ledger classification · journal structure · tax treatment · accounting assumptions · risk indicators · decision confidence · supporting reasoning · unresolved doubts.

## Secondary input

```text
Business Understanding Object          reference only
```

Used **only** for traceability, explanation, conflict identification and clarification context. **Clarification never changes the Business Understanding Object.**

The contract governing the inbound boundary is [`COMMUNICATION_RULES_ACCOUNTING_ENGINE.md`](COMMUNICATION_RULES_ACCOUNTING_ENGINE.md). **The sending engine owns the contract of what leaves it.** This document references it; it does not restate it.

The Clarification Engine **never communicates directly with Engine 1.**

## Receiving rules

**Preserve evidence provenance.** Source Type, Source ID, Evidence Reference, Timestamp, Confidence and Corroborated. **No origin may be merged into an anonymous fact.** A fact asserted only by a human and corroborated by nothing is a legitimate reason to raise a clarification — never a fact to rely on.

The Clarification Engine **must** preserve:

1. Evidence references.
2. Reasoning.
3. Assumptions.
4. Confidence.
5. Uncertainty.
6. Traceability.

The Clarification Engine **must never**:

- Modify previous artifacts.
- Hide conflicts.
- Remove assumptions.
- Increase confidence without new evidence.
- Create accounting decisions.

---

# 5. Output Contract

The Clarification Engine produces exactly one artifact: the **Clarification Request**.

```text
Clarification Request
├── Clarification ID                    identity only — IDENTITY ≠ INTELLIGENCE
├── Related Decision ID
├── Related Artifact Version            per the universal versioning rule
├── Missing Information
├── Detected Conflicts
├── Required Clarification
├── Reason Clarification Is Required
├── Affected Decision
├── Priority                            Critical | High | Medium | Low
├── Supporting Evidence References
├── Clarification Confidence
└── Status                              per the §7 state machine
```

## Every Clarification Request must answer

1. **What was unclear?**
2. **Why did it matter?**
3. **What information is required?**
4. **Which decision depends on it?**
5. **How important is it?**

## Related Artifact Version

A clarification request is always raised **against a specific version** of the Accounting Decision. Recording that version is what makes a stale request detectable: if the decision has since been rebuilt, the request is **Obsolete** and must not be answered against the newer version. See [`DATA_FLOW.md` §11](DATA_FLOW.md#11-artifact-versioning).

## Clarification ID

**Identity only** — identity, traceability, lifecycle tracking and audit history. Zero accounting meaning. It must never influence any decision, in this engine or any other. This is the system-wide **IDENTITY ≠ INTELLIGENCE** rule — see [`DATA_FLOW.md` §9](DATA_FLOW.md#9-identity--intelligence).

## Artifact ownership

> **`question_generator` creates the Clarification Request. The Clarification Engine owns it.**

The Clarification Engine owns the **Clarification Request**, **Clarification Status** and **Clarification History**. It does **not** own the Document Evidence Object, Business Understanding Object or Accounting Decision.

`question_generator` does not become an independent owner. The artifact is immutable after creation — see §7 and [`DATA_FLOW.md` §11](DATA_FLOW.md#11-artifact-versioning).

## Questions are outputs, not actions

**Engine 4 never asks users directly.** It produces a structured Clarification Request. Another system layer may later deliver that request to a user, accountant or external system. Engine 4 defines only *what is missing, why it matters, which decision depends on it, and how important it is.*

---

# 6. Absolute Boundaries

The Clarification Engine **MUST NEVER**:

1. Create journal entries.
2. Choose ledgers.
3. Decide accounting treatment.
4. Decide tax treatment.
5. Modify evidence.
6. Modify business understanding.
7. Modify accounting decisions.
8. Approve execution.
9. Reject execution.
10. Invent facts.
11. **Silently resolve conflicts.**
12. Convert assumptions into facts.
13. Convert uncertainty into certainty.
14. **Ask users directly.**
15. Bypass previous engines or bypass validation.

## Failure behaviour

If clarification cannot safely continue, it must return:

- What is known.
- What is unknown.
- Why clarification is required.
- Which decision is affected.

> **It must never guess.**

---

# 7. Clarification Lifecycle

Clarification is **not complete when a request is created.** It is complete only when the required information has been received and the responsible upstream engine has produced a new artifact version.

The Clarification Engine owns **every** transition, because it owns Clarification Status. It owns no **resolution** — resolution is an upstream engine emitting a new artifact version. Owning the status is not owning the outcome.

## States

| State | Entered when | Trigger | Transition owner |
|---|---|---|---|
| **Created** | `question_generator` assembles the Request | `stop_decision` returned *clarification required* | Clarification Engine |
| **Waiting for Information** | The Request is emitted | Request handed to the external actor | Clarification Engine |
| **Information Received** | An answer arrives in the system | External actor supplies a Clarification Answer | Clarification Engine — **records it, never interprets it** |
| **Obsolete** | A newer artifact version supersedes the one asked about | Upstream engine emits a version newer than Related Artifact Version | Clarification Engine |
| **Closed** | The uncertainty is gone | A new artifact version no longer carries the uncertainty that caused the request | Clarification Engine |

## Permitted transitions

```text
Created ──► Waiting for Information ──► Information Received ──► Closed
   │                  │                          │
   └──────────────────┴──────────────────────────┴──────► Obsolete
```

- `Closed` and `Obsolete` are **terminal**.
- `Obsolete` may be entered from **any** state.
- Nothing may go from `Created` straight to `Closed` — closure requires a new artifact version.

**Obsolete ≠ Closed.** Obsolete means the request was superseded before it was answered. Closed means the uncertainty no longer exists. Collapsing the two would hide the fact that a question went unanswered.

`decision_updater` records every transition with its timestamp, its trigger, and the related artifact versions. **No hidden lifecycle.**

## The loop lives outside this engine

```text
Accounting Decision
        ↓
Clarification Request
        ↓
External actor  (UI / API / human)          ← outside every engine
        ↓
Clarification Answer
        ↓
Engine 1 / 2 / 3 rebuilds the affected artifact
        ↓
New Accounting Decision
        ↓
Engine 4 runs again if needed
```

**Engine 4 never receives answers as a decision engine.** New information enters through the normal pipeline, preserving artifact ownership and avoiding backward mutation.

---

# 8. Knowledge Brain Boundary

The Knowledge Brain is **not part of Engine 4.** It is a system-level capability used by multiple engines. Full definition and interface: [`src/brain/README.md`](../src/brain/README.md).

## It may provide

Accounting standards · Indian accounting regulations · GST rules · company accounting policies · chart of accounts references · historical accounting patterns · accounting terminology · accounting guidance · previously resolved clarification patterns · relevant references · supporting explanations · likely implications.

## It may never

- Create clarification requests.
- Approve clarification.
- Make accounting decisions.
- Override engine outputs.

> **Knowledge flows into engines. Decision authority never leaves engines.**

The Brain is **advisory, never binding.** Any engine may ignore it, and an engine that acts against Brain knowledge records why in its own reasoning.

---

# 9. Internal Architecture

The Clarification Engine contains **exactly seven** sub-engines:

```text
Clarification Engine
├── understanding
├── uncertainty_detection
├── missing_information
├── question_generator
├── answer_understanding
├── decision_updater
└── stop_decision
```

No additions. No removals. No merges. **No renames** — these identities are part of the system contract and other engines already reference them.

## Flow

The flow is intentionally **one-directional**. Feedback occurs only through new artifact versions generated by the responsible upstream engine. Engine 4 never edits previous artifacts.

```text
Accounting Decision  (+ Business Understanding Object, reference only)
        ↓
missing_information      → Missing Information Result
        ↓
uncertainty_detection    → Uncertainty Analysis Result
        ↓
understanding            → Conflict Analysis Result
        ↓
stop_decision            → Clarification Necessity Result
        ↓
answer_understanding     → Clarification Priority Result
        ↓
question_generator       → Clarification Request
        ↓
decision_updater         → Clarification Status Result
```

## Name and responsibility

Three of these names were coined in Phase 1 for a clarification loop that ran *inside* the engine. That loop now runs outside it. The names are unchanged — identities are stable, responsibilities are not — and each assignment is deliberate:

| Sub-engine | Owns | Produces | Why this name owns this responsibility |
|---|---|---|---|
| **`missing_information`** | Missing information detection | Missing Information Result | Identical then and now: it finds what is absent. |
| **`uncertainty_detection`** | Uncertainty analysis | Uncertainty Analysis Result | Detection is the act; analysis is its output. The same faculty named from opposite ends. |
| **`understanding`** | Conflict analysis | Conflict Analysis Result | A contradiction cannot be found without comprehending evidence, understanding and decision *together*. In Phase 1 it comprehended the case and located the doubts in it; it now comprehends the case and locates the contradictions in it. Same faculty, sharper target. |
| **`stop_decision`** | Clarification necessity | Clarification Necessity Result | It was always the go/no-go gate on the clarification path. Phase 1: *is questioning complete?* Now: *is clarification required at all?* Both are one binary judgement about whether clarification runs. |
| **`answer_understanding`** | Clarification prioritisation | Clarification Priority Result | Priority is a judgement about **answers**. Nothing can be ranked without understanding how much the answer to each would change the decision. Phase 1 it reasoned about answers received; it now reasons about the weight of answers not yet received. It is the answer-centric component in both eras. |
| **`question_generator`** | Clarification building | Clarification Request | It formulates what is asked. The Clarification Request *is* what Phase 1 called the Question Set, in structured form — what is missing, why it matters, what is needed. Generating the question is generating the request. |
| **`decision_updater`** | Clarification tracking | Clarification Status Result | It is the component that knows the relationship between a clarification and the **state of the decision**. Phase 1 it carried answers back so the decision could be remade; it now links each clarification to the decision version it was raised against and marks it obsolete when a newer version supersedes it. Version-and-state tracking in both eras. |

Every Result carries **confidence** and **evidence references**. No Result may omit them.

---

# 10. Sub-Engine Specifications

---

## 10.1 `missing_information`

### Purpose
Identify every piece of information required to safely continue that is currently unavailable.

### Owns
Missing information identification.

### Name and responsibility
Name and role are identical. It found what was absent in Phase 1; it finds what is absent now.

### Receives
The Accounting Decision, and the Business Understanding Object (reference only).

### Produces
**Missing Information Result** — missing facts · missing relationships · missing supporting evidence · affected accounting decisions · confidence · evidence references.

### Allowed Actions
Compare required information against available information · detect absent information · preserve traceability.

### Forbidden Actions
Infer missing facts · invent values · modify previous artifacts · ask users directly.

### Failure Behaviour
If completeness cannot be determined, **preserve uncertainty and report incomplete detection rather than assuming completeness.** An undetermined completeness is never recorded as complete.

---

## 10.2 `uncertainty_detection`

### Purpose
Determine whether available information is reliable enough for downstream execution.

### Owns
Uncertainty evaluation.

### Name and responsibility
Detection is the act; analysis is its output. The Phase 1 name describes what it does; the artifact name describes what it produces.

### Receives
Missing Information Result and the Accounting Decision.

### Produces
**Uncertainty Analysis Result** — uncertainty sources · uncertainty severity · confidence impact · affected decisions · supporting reasoning.

### Allowed Actions
Measure uncertainty · classify uncertainty · preserve supporting evidence.

### Forbidden Actions
Increase confidence without evidence · remove uncertainty · modify accounting reasoning.

### Failure Behaviour
**Unknown uncertainty remains visible. Never convert uncertainty into certainty.** Uncertainty that cannot be classified is recorded as unclassified, not dropped.

---

## 10.3 `understanding`

### Purpose
Detect contradictions between evidence, understanding and accounting decisions.

### Owns
Conflict identification.

### Name and responsibility
A contradiction cannot be found without comprehending all three artifacts together. In Phase 1 this component comprehended the case and located the **doubts** in it; it now comprehends the case and locates the **contradictions** in it. Same faculty, sharper target.

### Receives
The Accounting Decision, the Business Understanding Object, and the Missing Information Result.

### Produces
**Conflict Analysis Result** — detected conflicts · conflicting assumptions · conflicting reasoning · conflict severity · affected accounting decisions.

### Allowed Actions
Identify contradictions · preserve all conflicting information · maintain traceability.

### Forbidden Actions
**Resolve conflicts** · discard conflicting evidence · **choose one interpretation**.

### Failure Behaviour
**Every detected conflict remains visible until resolved by the responsible engine.** A conflict that cannot be characterised is still recorded, marked as uncharacterised.

---

## 10.4 `stop_decision`

### Purpose
Determine whether clarification is actually required.

Not every uncertainty deserves a clarification request. Some uncertainty has no effect on accounting treatment; some changes the entire accounting decision. This sub-engine prevents unnecessary clarification while ensuring decision-critical uncertainty is never ignored.

### Owns
Clarification necessity.

### Name and responsibility
It was always the go/no-go gate on the clarification path. Phase 1 asked *is questioning complete?*; it now asks *is clarification required at all?* Both are one binary judgement about whether clarification runs.

### Receives
Missing Information Result, Uncertainty Analysis Result, Conflict Analysis Result, and the Accounting Decision.

### Produces
**Clarification Necessity Result** — clarification required · clarification optional · clarification unnecessary · business impact · accounting impact · supporting reasoning.

### Allowed Actions
Evaluate decision impact · determine necessity · preserve reasoning.

### Forbidden Actions
Generate clarification requests · modify accounting decisions · modify uncertainty.

### Failure Behaviour
**If necessity cannot be determined safely, default to Clarification Required. Never silently ignore uncertainty.** The asymmetry is deliberate: an unnecessary question costs time, a missed one costs correctness.

---

## 10.5 `answer_understanding`

### Purpose
Determine the order in which clarification should occur. Critical accounting blockers must always be resolved before cosmetic or informational clarification.

### Owns
Clarification priority.

### Name and responsibility
Priority is a judgement about **answers**. Nothing can be ranked without understanding how much the answer to each clarification would change the decision. In Phase 1 this component reasoned about answers received; it now reasons about the weight of answers not yet received. It is the answer-centric component in both eras.

### Receives
Clarification Necessity Result.

### Produces
**Clarification Priority Result** — priority level · affected decision · business impact · accounting impact · urgency reasoning.

Priority levels: **Critical · High · Medium · Low.**

### Allowed Actions
Prioritise clarification · group related clarification · determine execution order.

### Forbidden Actions
Remove clarification requirements · modify accounting reasoning · modify previous artifacts.

### Failure Behaviour
**Unknown priority defaults to High until sufficient information exists.** Under-prioritising an unknown is the more expensive error.

---

## 10.6 `question_generator`

### Purpose
Construct the canonical Clarification Request.

### Owns
Clarification Request creation.

### Name and responsibility
It formulates what is asked. The Clarification Request *is* what Phase 1 called the Question Set, in structured form — what is missing, why it matters, what is needed. Generating the question is generating the request.

### Receives
Outputs from every previous Clarification sub-engine.

### Produces
The **Clarification Request** — the twelve components of §5.

### Allowed Actions
Assemble clarification · merge clarification components · preserve evidence references.

### Forbidden Actions
Invent clarification · modify upstream decisions · hide uncertainty · rewrite reasoning.

### Failure Behaviour
**Produces an incomplete Clarification Request while preserving every unresolved issue.** An incomplete request that names what it could not determine is correct output; a complete-looking request that dropped an issue is not.

---

## 10.7 `decision_updater`

### Purpose
Track the lifecycle of every clarification request.

### Owns
Clarification lifecycle · clarification status · clarification history.

### Name and responsibility
It is the component that knows the relationship between a clarification and the **state of the decision**. In Phase 1 it carried answers back so the decision could be remade; it now links each clarification to the decision version it was raised against, and marks it obsolete when a newer version supersedes it. Version-and-state tracking in both eras.

### Receives
The Clarification Request.

### Produces
**Clarification Status Result** — current status · timestamps · related artifact versions · resolution history · audit trail.

### Allowed Actions
Track progress · maintain history · link clarification to artifact versions.

### Forbidden Actions
**Resolve clarification** · modify decisions · approve execution.

### Failure Behaviour
**Preserve complete audit history even if clarification remains unresolved.** History is never trimmed because a request went nowhere.

---

# 11. Confidence Model

Engine 4 introduces **Clarification Confidence**.

> **"How confident is the system that every decision-blocking uncertainty has been correctly identified?"**

Note what it does *not* measure: it says nothing about whether the accounting is right, only about whether the system has found everything that could make it wrong.

## Influenced by

```text
Clarification Confidence

    Evidence Reliability          (Engine 1)
  + Understanding Confidence      (Engine 2)
  + Decision Confidence           (Engine 3)
  + Missing Information
  + Detected Conflicts
  + Uncertainty Severity
```

## Rules

> **Clarification Confidence may never exceed upstream confidence.**
>
> **Higher certainty cannot emerge from weaker evidence.**

This is the system-wide layered-confidence rule at its fourth level — **confidence can only decrease downstream unless new evidence is introduced.** See [`DATA_FLOW.md` §10](DATA_FLOW.md#10-confidence-across-engines).

| Engine | Confidence | Asks |
|---|---|---|
| Input | Evidence confidence | Was information extracted correctly? |
| Understanding | Understanding confidence | Was the business event understood correctly? |
| Accounting | Decision confidence | Is the accounting treatment likely correct? |
| **Clarification** | **Clarification confidence** | **Has every decision-blocking uncertainty been found?** |
| Validation | Validation confidence | Is this safe to approve? *(declared; specified with Engine 5)* |

---

# 12. Conflict Handling

**Engine 4 never resolves conflicts.**

Every conflict must remain visible until one of exactly two events occurs:

1. **New information enters the system** and the responsible upstream engine produces a new artifact version.
2. **The conflict is explicitly accepted** by a future validation or human decision process.

> **Clarification exists to expose uncertainty, never to hide it.**

A Clarification Request carrying an unresolved conflict is correct output, not a failure.

---

# 13. Communication Contract

## Inbound — Accounting Engine → Clarification Engine

Governed by [`COMMUNICATION_RULES_ACCOUNTING_ENGINE.md`](COMMUNICATION_RULES_ACCOUNTING_ENGINE.md). **One contract per boundary**; the sending engine owns it.

## Internal — between the seven sub-engines

Governed by [`COMMUNICATION_RULES_CLARIFICATION_INTERNAL.md`](COMMUNICATION_RULES_CLARIFICATION_INTERNAL.md).

## Outbound — Clarification Engine → Validation Engine

**Placeholder.** The full boundary contract is authored when Engine 5 is specified, and this engine owns it.

What is already fixed:

- **Artifact sent:** Clarification Request.
- **Creator:** `question_generator`. **Owner:** Clarification Engine.
- **Validation receives both** the Accounting Decision (from the Accounting Engine, the primary artifact to validate) **and** the Clarification Request (whether unresolved uncertainty exists). The Request is **supplementary, not a replacement** — Validation cannot validate a Clarification Request alone.
- **Engine 4 never validates, approves or executes decisions.**

## Decision Authority

Every communication contract in this system carries this block unchanged:

> **The sending engine owns the meaning of its artifact.**
>
> The receiving engine **may** consume, analyze, and produce its own artifact.
> The receiving engine **may not** rewrite upstream artifacts, change upstream decisions, or remove uncertainty.

---

# 14. Quality Standard

## The Clarification Engine succeeds when

- ✅ Every decision-blocking uncertainty is identified.
- ✅ Only necessary clarification is requested.
- ✅ Uncertainty is preserved.
- ✅ Ownership is preserved — no decision moves.
- ✅ Reliability improves without any fact being invented.

## The Clarification Engine fails when

- ❌ Uncertainty is missed.
- ❌ Unnecessary clarification is generated.
- ❌ Assumptions are hidden.
- ❌ A conflict is silently resolved.
- ❌ Certainty is unsupported.

Note the asymmetry, as in Engines 1–3: a Clarification Request naming an uncertainty that turns out to be harmless is a **success**. A clean pipeline that missed one blocking uncertainty is a **failure**, even if the resulting entry happened to be right.

---

# 15. Final Validation Checklist

## Architecture
- [x] Exactly seven Clarification sub-engines. No additions, removals or renames.
- [x] Clarification owns only clarification.
- [x] Every sub-engine owns exactly one decision; no overlaps.
- [x] Every sub-engine has all seven headings plus name-and-responsibility.

## Artifacts
- [x] Clarification Request defined once, used consistently.
- [x] Engine 4 never modifies the Document Evidence Object, Business Understanding Object or Accounting Decision.
- [x] Related Artifact Version present, per the universal versioning rule.
- [x] Clarification ID protected by IDENTITY ≠ INTELLIGENCE.

## Authority and lifecycle
- [x] Decision authority defined — eight rows.
- [x] Parent assembles; never overrides or rewrites sub-engine decisions.
- [x] Clarification lifecycle fully defined; every transition has a trigger and an owner.
- [x] Every communication boundary has exactly one owner: the sending engine.

## Safety
- [x] Clarification Confidence defined separately, and never exceeds upstream confidence.
- [x] Every uncertainty remains visible; no hidden assumptions.
- [x] No sub-engine invents information.
- [x] No sub-engine silently resolves conflicts.
- [x] Knowledge Brain referenced only as a shared knowledge provider.
- [x] No code created. No implementation created.

---

## Related documents

- [`ENGINE_3_ACCOUNTING_ENGINE_RULES.md`](ENGINE_3_ACCOUNTING_ENGINE_RULES.md) — the engine that produces this engine's input.
- [`COMMUNICATION_RULES_ACCOUNTING_ENGINE.md`](COMMUNICATION_RULES_ACCOUNTING_ENGINE.md) — the inbound boundary contract.
- [`COMMUNICATION_RULES_CLARIFICATION_INTERNAL.md`](COMMUNICATION_RULES_CLARIFICATION_INTERNAL.md) — communication between the seven sub-engines.
- [`SUB_ENGINE_RESPONSIBILITIES.md`](SUB_ENGINE_RESPONSIBILITIES.md) — the canonical system-wide sub-engine map.
- [`DATA_FLOW.md`](DATA_FLOW.md) — artifact ownership, decision authority, IDENTITY ≠ INTELLIGENCE, confidence, versioning.
- [`SYSTEM_BOUNDARIES.md`](SYSTEM_BOUNDARIES.md) — system-wide forbidden behaviour.
- [`../src/brain/README.md`](../src/brain/README.md) — the Knowledge Brain and its interface.
