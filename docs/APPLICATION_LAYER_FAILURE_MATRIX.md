# Application Layer — Failure Matrix

> **Precedence level 3.** Every failure, its detection, its owner, whether it retries, and where it escalates.
>
> **The line this document exists to hold:**
>
> > **Business failures belong to sub-engines. Runtime failures belong to the Application Layer.** — INV-4
>
> Confusing them is the defect this matrix prevents. Retrying a business failure re-runs reasoning that already succeeded, and could produce a **different conclusion from identical input** — destroying reproducibility.

---

## The test that separates them

```text
Did the engine REACH A CONCLUSION?

  YES → business outcome. It produced an artifact. NEVER retried.
        Even "I cannot determine this" is a conclusion.

  NO  → runtime failure. It produced NOTHING. Retried by the Application Layer.
```

**An engine that produces an artifact has succeeded**, however unwelcome the content.

---

## Business failures — engine-owned, never retried

| Failure | Detected by | Owner | Produces | Retryable | Where it goes |
|---|---|---|---|---|---|
| Unreadable / corrupt / zero-byte document | Engine 1 | Engine 1 | Document Evidence Object recording the failure | **No** | Understanding, carrying the failure |
| Illegible photograph | Engine 1 | Engine 1 | Low-confidence evidence | **No** | Travels; likely becomes a doubt |
| Contradictory dates | Engine 2 | Engine 2 | Business Understanding Object with the conflict **unresolved** | **No** | Accounting |
| Missing fact that changes treatment | Engine 3 | Engine 3 | Accounting Decision carrying a doubt | **No** | Clarification |
| Vendor matching two ledgers | Engine 3 | Engine 3 | Doubt, not a guess | **No** | Clarification |
| Ambiguous separator — `1,00,000` vs `1.00000` | Engine 2/3 | that engine | Ambiguity travels, never normalised | **No** | Clarification |
| Clarification unanswerable | Engine 4 | Engine 4 | Recorded; cannot proceed | **No** | `Failed` |
| Debit ≠ credit | Engine 5 | Engine 5 | Validation Decision, Critical finding | **No** | `Failed` on `Rejected` |
| Closed accounting period | Engine 5 | Engine 5 | Critical finding | **No** | Must be caught **here**, never discovered by Execution |
| Consequences warrant a human | Engine 5 | Engine 5 | `Approved With Warning` | **No** | `WaitingForApproval` ⚠️ **PROPOSED — Amendment 2, not approved** |
| Reasoning incomplete | Engine 5 | Engine 5 | `Clarification Required` | **No** | Clarification → Engine 3 new version → **Validation again** |
| Transport failure to Tally | Engine 6 | **Engine 6** | Execution Result recording it | **Engine 6's own retry** | `posting_manager` reposts, bounded by the idempotency key |

**None of the above is ever retried by the Application Layer.** Each is a valid conclusion recorded in an artifact.

---

## Runtime failures — Application Layer owned

| Failure | Detected by | Owner | Produces | Retryable | Escalation |
|---|---|---|---|---|---|
| **Engine timeout** | Application Layer | Application Layer | **Nothing** | **Yes** | Budget exhausted → `Failed` |
| **Engine crash** | Application Layer | Application Layer | **Nothing** | **Yes** | Budget exhausted → `Failed` |
| **Unexpected exception** | Application Layer | Application Layer | **Nothing** | **Yes** | Budget exhausted → `Failed`. **Never swallowed** |
| **Schema violation** — engine returned an artifact failing its contract | Application Layer | Application Layer | **Nothing accepted** | **No** | Immediate `Failed`. A defect, not a transient fault. **Never repaired** |
| **State store unavailable** | Application Layer | Application Layer | Nothing | **Yes** | Refuse to start or transition. **Never proceed with unknown state** |
| **Audit sink unavailable** | Application Layer | Application Layer | Nothing | **Yes** | **Refuse to transition.** An untraceable transition is worse than a halted one |
| **Missing required configuration** | Application Layer | Application Layer | Nothing | **No** | **Refuse to start**, naming the key. Never a default (AL-INV-14) |
| **Disallowed transition attempted** | Application Layer | Application Layer | Nothing | **No** | Reject. Never force it, never log-and-permit |

---

## Why schema violations are not retryable

An engine that returns a malformed artifact will return the same malformed artifact on the next attempt — it is a **defect in the engine**, not a transient fault. Retrying wastes attempts and hides the bug.

**And the Application Layer must never repair it.** Repairing means modifying an artifact (AL-INV-7 forbids) and inferring intent (INV-4 forbids). A malformed artifact is rejected, recorded, and the transaction fails loudly.

---

## Escalation paths

```text
Runtime failure
      │
      ├─ retryable? ── no ──► Failed. Artifacts preserved. Nothing fabricated.
      │
      └─ yes
           │
           └─ attempts < APP_RETRY_MAX_ATTEMPTS_PER_ENGINE?
                    │
                    ├─ yes ──► restart from LAST COMPLETED ARTIFACT
                    │
                    └─ no  ──► Failed. Human intervention. resume_transaction()
                               restarts from the last completed artifact.
```

**`Failed` is never terminal by fabrication.** No output is invented to escape it.

---

## What is preserved when anything fails

| | |
|---|---|
| **Completed artifacts** | **Preserved.** Never deleted, never edited |
| **Transaction ID** | **Preserved.** A correction or resume uses the same one |
| **Partial artifacts** | **Never exist.** An engine that cannot complete produces nothing |
| **Audit trail** | **Append-only.** The failure is recorded, never overwritten |
| **State** | The last **completed** state. A crash mid-transition leaves the previous state intact (AL-INV-3) |

> **A half-built artifact is more dangerous than none.** — `DATA_FLOW §14`

---

## Failures that must never happen, and what makes them impossible

| Must never happen | Prevented by |
|---|---|
| A decision reaches Tally without Validation | AL-INV-6 · transition table has no `Accounting → Execution` |
| `Approved With Warning` posts without a human | AL-INV-9 ⚠️ *depends on Amendment 2, PROPOSED* · only `release_waiting_for_approval()` leaves that state |
| The same voucher posts twice | Idempotency key: Decision ID + Version + Destination · `retry_engine()` always rejects Engine 6 |
| A retry produces a different conclusion | AL-INV-12 · only runtime failures retry |
| An engine skips a stage | AL-INV-6 · every transition validated against the allowed table |
| Engine 6 returns work upstream | AL-INV-11 · Engine 6 has no upstream call |
| A partial artifact is persisted | AL-INV-10 · engine failure produces nothing |
| A transaction is in two states | AL-INV-2 · one row per Transaction ID |
| A transition is half-applied | AL-INV-3 · single committed write |
| A silent default governs a retry | AL-INV-14 · missing config refuses startup |
| A transaction is cancelled | No `Cancelled` state exists (AL-INV-13) |

---

## The failure this whole matrix guards against

**A wrong entry posting silently.**

Not a crash — a crash is visible. The dangerous failure is the confident wrong answer that nobody checks, because the system is usually right.

Nothing in the Application Layer can cause it directly — it owns no reasoning. But it could **enable** it, by skipping Validation, by releasing a held decision without a human, by retrying until a different answer appeared, or by repairing a malformed artifact into a plausible one.

**Every one of those four is structurally impossible above, not merely discouraged.**
