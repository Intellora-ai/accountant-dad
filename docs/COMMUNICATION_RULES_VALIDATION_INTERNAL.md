# Communication Rules — Validation Engine, Internal

> **Precedence level 4 — Communication Contracts.** Subordinate to [`SYSTEM_INVARIANTS.md`](SYSTEM_INVARIANTS.md). Where this document contradicts an invariant, this document is wrong.

> How the six Validation sub-engines communicate with one another.
>
> Companion to [`ENGINE_5_VALIDATION_ENGINE_RULES.md`](ENGINE_5_VALIDATION_ENGINE_RULES.md). **Specification only — no implementation.**
>
> This document governs communication *inside* Engine 5. The boundaries into it are governed by [`COMMUNICATION_RULES_ACCOUNTING_ENGINE.md`](COMMUNICATION_RULES_ACCOUNTING_ENGINE.md) and [`COMMUNICATION_RULES_CLARIFICATION_ENGINE.md`](COMMUNICATION_RULES_CLARIFICATION_ENGINE.md).

---

# 1. Flow

```text
Accounting Decision · Clarification Request · reference artifacts
                            ↓
                     data_validation                ← the only gate
                            ↓
                  Data Validation Result
                            │
        ┌───────────────────┼───────────────────┬───────────────────┐
        ↓                   ↓                   ↓                   ↓
accounting_validation  tax_validation   duplicate_detection   risk_assessment
        ↓                   ↓                   ↓                   ↓
 Accounting          Tax Validation      Duplicate            Risk
 Validation Result   Result              Detection Result     Assessment
        │                   │                   │                   │
        └───────────────────┴─────────┬─────────┴───────────────────┘
                                      ↓
                             validation_decision
                                      ↓
                             Validation Decision
```

`risk_assessment` reads the other three Results in addition to the Data Validation Result — posting risk depends on what the other validators found. It is the one sub-engine whose input is the others' output, and it still decides nothing about approval.

---

# 2. The Gate and the Fan-Out

## `data_validation` is the only sub-engine that may stop the pipeline

If required artifacts are missing, incomplete or version-incompatible, there is nothing to validate. It reports **every** missing component — never the first one found — and validation ends there.

## Once artifacts exist, all four validators always run

**No validator is skipped because another failed.**

```text
✗  accounting error found → stop → tax error never discovered
✓  accounting error found → tax validation still runs → both reported
```

A transaction with an accounting error and a tax error must report **both**. A sequential chain would surface the accounting error, hide the tax error behind it, and produce a second rejection round after the first was fixed — the user experiences one problem at a time when the system already knew about two.

This is the structural form of the invariant in Rule 5: **every failed validation rule remains visible.**

---

# 3. Communication Rules

---

## Rule 1 — Sub-engines communicate only through defined outputs

Each sub-engine publishes exactly one named Result, and that Result is the entirety of what siblings may see.

| Sub-engine | Publishes |
|---|---|
| `data_validation` | Data Validation Result |
| `accounting_validation` | Accounting Validation Result |
| `tax_validation` | Tax Validation Result |
| `duplicate_detection` | Duplicate Detection Result |
| `risk_assessment` | Risk Assessment |
| `validation_decision` | Validation Decision |

---

## Rule 2 — No hidden communication

No shared mutable state. No side channels. No implicit coupling through anything other than a published Result.

If a sub-engine needs something a sibling knows, that something must be part of the sibling's Result — named, traceable and challengeable. If it is not in the Result, it is not available, and the correct response is to record it as an unknown, not to reach for it.

---

## Rule 3 — No sub-engine modifies another sub-engine's output

A Result is **read-only** to every sibling, permanently — and so is every upstream artifact.

A sub-engine that believes a sibling's Result is wrong does not correct it. It records the disagreement in its own Result, and the disagreement travels into the Validation Decision.

---

## Rule 4 — Confidence must travel with every output

Every Result carries confidence. No Result may omit it, and **no Result may raise it**.

> **Validation Confidence never exceeds the weakest critical confidence it depends on.**

Governed by [`SYSTEM_INVARIANTS.md` INV-2](SYSTEM_INVARIANTS.md#inv-2--confidence-changes-only-when-evidence-changes) — confidence is recalculated when evidence changes, never because a validator reasoned harder. **Validation cannot create confidence. It can only evaluate the confidence that arrived.**

---

## Rule 5 — Every failed validation rule remains visible

**No validation finding may disappear inside the pipeline.**

A finding that enters a Result reaches the Validation Decision. It is never dropped for being redundant, never merged into a summary that loses its rule identity, never suppressed because a higher-severity finding already blocks execution.

Severity is never hidden or downgraded without evidence. A **Low** finding is still recorded permanently.

---

## Rule 6 — Every finding names its responsible engine

A finding without an owner cannot be acted on. Every one points back to Engine 1, 2, 3 or 4.

```text
✗ "Validation failed."
✓ "Validation failed because the Accounting Decision lacks supporting evidence
   for its ITC claim — responsible engine: Accounting."
```

Each finding carries: what failed · why it failed · the responsible engine · the affected artifact · blocking severity · the recommended next step.

---

## Rule 7 — Validation reports; it never repairs

No sub-engine may fix what it detects. Not an accounting error, not a missing evidence reference, not a broken traceability chain, not an unbalanced journal.

A repair inside Validation would mean the engine reviewing the work had become a co-author of it — and there would be nothing left to review it in turn.

---

## Rule 8 — `validation_decision` assembles; it does not rewrite

| `validation_decision` CAN | `validation_decision` CANNOT |
|---|---|
| Combine validation outputs | Invent findings |
| Organize them | **Hide failures** |
| Determine Validation Status from them | Override a sub-engine |
| Present the final reasoning | Remove uncertainty |
| | Approve while a Critical finding stands |
| | Create accounting decisions |

**`validation_decision` creates the Validation Decision. The Validation Engine owns it.** It does not become an independent owner.

---

# 4. Status Assembly

`validation_decision` reads five Results and produces one status. The mapping is mechanical, not discretionary:

| Condition | Status |
|---|---|
| Any **Critical** finding stands unresolved | **Rejected** |
| Missing information could make the decision correct · an unresolved Clarification Request blocks | **Clarification Required** |
| No blocking finding, but `risk_assessment` recommends human attention | **Approved With Warning** |
| No blocking finding, acceptable risk | **Approved** |

**`Approved With Warning` and `Clarification Required` are not interchangeable.** The first says the reasoning is sound and the consequences warrant a human; the second says the reasoning is incomplete. Collapsing them would send a correct entry back for a question nobody can answer — or send an incomplete one to a human who has nothing to decide.

`risk_assessment` never sets a status. Its recommendation is an input to this table, and `validation_decision` is the only sub-engine that reads the table.

---

# 5. What These Rules Protect

Every rule above defends one property: **an approval means something a rejection does not, and both can be explained down to the rule and the engine that produced them.**

Break any one and that property goes:

- Allow a validator to be skipped because an earlier one failed, and the system reports one problem while knowing two.
- Allow a finding to be suppressed as redundant, and a rejection stops listing what actually has to be fixed.
- Allow a finding to omit its responsible engine, and *"Validation failed"* becomes the whole message.
- Allow a validator to repair what it found, and the reviewer became an author — there is nothing left that did not participate.
- Allow confidence to be raised, and the number stops meaning anything.
- Allow `validation_decision` to soften a Critical finding, and approval no longer means safe.
- Collapse `Approved With Warning` into `Clarification Required`, and *"correct but a human should look"* has no way to be said.

None of these fail loudly. They all produce output that looks cleaner than the honest version — which is exactly why they are prohibitions rather than guidance.

---

## Related documents

- [`ENGINE_5_VALIDATION_ENGINE_RULES.md`](ENGINE_5_VALIDATION_ENGINE_RULES.md) — the Validation Engine specification.
- [`COMMUNICATION_RULES_ACCOUNTING_ENGINE.md`](COMMUNICATION_RULES_ACCOUNTING_ENGINE.md) · [`COMMUNICATION_RULES_CLARIFICATION_ENGINE.md`](COMMUNICATION_RULES_CLARIFICATION_ENGINE.md) — the inbound boundary contracts.
- [`DATA_FLOW.md`](DATA_FLOW.md) — artifact ownership, decision authority, IDENTITY ≠ INTELLIGENCE.
- [`SYSTEM_BOUNDARIES.md`](SYSTEM_BOUNDARIES.md) — system-wide forbidden behaviour.
