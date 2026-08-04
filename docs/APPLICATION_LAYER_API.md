# Application Layer API

> **Precedence level 3.** Interface definition only — **no implementation.**
>
> Six operations. Nothing else is public. Anything not listed here is internal and may not be called from outside `src/services/`.
>
> ⚠️ `release_waiting_for_approval()` depends on **Amendment 2**, which is **PROPOSED, not approved** — see [`ARCHITECTURE_AMENDMENTS.md`](ARCHITECTURE_AMENDMENTS.md).

---

## Rules that hold for every operation

```text
No operation returns a decision, a treatment, a ledger, a rate or an instruction.
No operation modifies an artifact.
No operation queries the Brain.
Every operation is idempotent, or explicitly documents why it cannot be.
Every failure is loud. Nothing returns a default on error.
```

---

## `start_transaction()`

**Purpose** — Begin a new transaction. The **only** way a Transaction ID comes into existence.

| | |
|---|---|
| **Inputs** | One or more source documents · optional human business context |
| **Returns** | Transaction ID |
| **Preconditions** | At least one document supplied |
| **Postconditions** | Transaction ID created and never reused · state is `Input` · audit records creation · Engine 1 started |
| **Invariants preserved** | AL-INV-1 (ID immutable) · AL-INV-2 (exactly one state) |
| **Failure conditions** | No document supplied → reject, create nothing · state store unavailable → reject, create nothing · **never returns a Transaction ID it did not persist** |
| **Idempotent** | **No.** Two calls create two transactions. Two identical documents submitted twice are two submissions — deduplication is a business question and belongs to an engine, not here |

> **Human business context is evidence, not instruction.** It is passed to Engine 1 as evidence and is never binding on any engine. See the open conflict in `ARCHITECTURE_AMENDMENTS.md`.

---

## `resume_transaction()`

**Purpose** — Continue a transaction that stopped at a runtime failure. Restarts from the **last completed artifact**.

| | |
|---|---|
| **Inputs** | Transaction ID |
| **Returns** | The state resumed into |
| **Preconditions** | Transaction exists · state is `Failed` · at least one completed artifact exists |
| **Postconditions** | State returns to the stage that failed · **no artifact created, modified or deleted** · audit records the resume |
| **Invariants preserved** | AL-INV-7 (artifacts immutable) · AL-INV-10 (engine failure is not an artifact) · AL-INV-3 (atomic) |
| **Failure conditions** | Unknown Transaction ID → reject · state is not `Failed` → reject, **never force a transition** · no completed artifact → reject, restarting from nothing is starting over |
| **Idempotent** | **Yes.** Resuming an already-resumed transaction is a no-op |

**Never re-runs a completed stage.** Reasoning that succeeded is not repeated — that would risk a different conclusion from identical input (AL-INV-12).

---

## `retry_engine()`

**Purpose** — Retry a single engine execution after a runtime failure.

| | |
|---|---|
| **Inputs** | Transaction ID · engine identifier |
| **Returns** | Attempt number, and whether the retry budget is now exhausted |
| **Preconditions** | Transaction exists · the named engine is the one that failed · failure class is **retryable** (timeout · crash · unexpected exception) · attempts below `APP_RETRY_MAX_ATTEMPTS_PER_ENGINE` |
| **Postconditions** | Engine restarted from its input artifact · attempt count incremented · audit records the attempt · on exhaustion, state → `Failed` |
| **Invariants preserved** | AL-INV-12 (retry never changes a conclusion) · AL-INV-10 |
| **Failure conditions** | Failure class **not** retryable → reject and say why · budget exhausted → state `Failed`, never a silent extra attempt · **Engine 6 → always reject** |
| **Idempotent** | **No.** Each call is one attempt, counted |

### Engine 6 is excluded, deliberately

```text
Engine 6 reposts a transport-failed voucher.        posting_manager
The Application Layer restarts a crashed engine.    here
```

`COMM_EXECUTION_INTERNAL:131` — *"the Application Layer never decides that a voucher should be sent again."* Calling `retry_engine()` for Engine 6 is **always** an error, because it would be a re-post wearing a retry's clothing. A *crashed* Engine 6 is restarted by `resume_transaction()`, and idempotency (Decision ID + Version + Destination) prevents a double post.

---

## `release_waiting_for_approval()` ⚠️

**Purpose** — A human releases a transaction held on `Approved With Warning`.

⚠️ **Requires Amendment 2. Until it is approved this operation does not exist.**

| | |
|---|---|
| **Inputs** | Transaction ID · identity of the releasing human |
| **Returns** | The state moved into (`Execution`) |
| **Preconditions** | State is `WaitingForApproval` · Validation Decision is `Approved With Warning` · the releasing identity is recorded |
| **Postconditions** | State → `Execution` · Engine 6 started · audit records **who** released and **when** · the warning travels with the work and is referenced by the Execution Result |
| **Invariants preserved** | AL-INV-9 · AL-INV-6 (no skipping) · AL-INV-4 (no engine observes state) |
| **Failure conditions** | State is not `WaitingForApproval` → reject · no releasing identity → reject; an anonymous release defeats the gate's purpose · **never auto-releases**, on any timer, under any condition |
| **Idempotent** | **Yes.** Releasing an already-released transaction is a no-op, never a second execution |

**There is no timeout on this state.** A transaction may wait indefinitely. Auto-release after a delay would mean *"a human should look at this, unless nobody does, in which case proceed"* — which is not a gate.

**Engine 6 never learns a gate existed** (`COMM_VALIDATION_ENGINE:71`) — which is precisely why it cannot accidentally skip one.

---

## `get_transaction_state()`

**Purpose** — Report a transaction's current state. Read-only.

| | |
|---|---|
| **Inputs** | Transaction ID |
| **Returns** | Exactly one state · when it was entered · what triggered it |
| **Preconditions** | Transaction exists |
| **Postconditions** | **None.** Nothing is changed, created or started |
| **Invariants preserved** | AL-INV-2 (returns exactly one state, never zero or two) |
| **Failure conditions** | Unknown Transaction ID → reject, never an empty or default state |
| **Idempotent** | **Yes.** Pure read |

**Never callable by an engine.** AL-INV-4 — no engine may observe state. This exists for humans and operational tooling.

---

## `get_transaction_history()`

**Purpose** — The full, append-only transition history. Answers *"why is this transaction here"* without inference.

| | |
|---|---|
| **Inputs** | Transaction ID |
| **Returns** | Every transition in order: from · to · timestamp · trigger · engine involved · retry attempt · releasing identity where applicable |
| **Preconditions** | Transaction exists |
| **Postconditions** | **None.** Pure read |
| **Invariants preserved** | AL-INV-3 — every recorded transition is one that actually completed |
| **Failure conditions** | Unknown Transaction ID → reject · **history is never truncated, compacted or summarised** |
| **Idempotent** | **Yes** |

**Returns workflow history only.** It never returns artifact content, decision reasoning or confidence — those belong to the artifacts and the engines that own them.

---

## Not in this API, and why

| Absent | Why |
|---|---|
| `cancel_transaction()` | **No `Cancelled` state exists.** *"If a state is not in the locked state machine, it does not exist."* |
| `set_transaction_state()` | State changes only via defined transitions. An arbitrary setter would void AL-INV-6 |
| `modify_artifact()` | AL-INV-7. Correction is a new version, produced by the owning engine |
| `skip_stage()` | AL-INV-6. `DATA_FLOW:283` — no stage may be bypassed, however obvious |
| `override_validation()` | The Application Layer owns no decision. A human who disagrees provides new evidence; Engine 3 issues a new version; Validation runs again |
| `query_brain()` | AL-INV-8. Engines query the Brain; the Application Layer never does |
| `force_complete()` | `Completed` follows an Execution Result. Forcing it would fabricate the claim that something posted |

---

## Configuration this API depends on

Every value is **REQUIRED with no default** (AL-INV-14):

```text
APP_RETRY_MAX_ATTEMPTS_PER_ENGINE    retry_engine() budget
APP_ENGINE_TIMEOUT_SECONDS           when an engine counts as timed out
APP_RETRY_BACKOFF                    spacing between attempts
APP_ENGINE_ENDPOINTS                 where each engine is reached
APP_STATE_STORE                      where state and history live
APP_AUDIT_SINK                       where the audit trail is written
```

**A missing value means the Application Layer refuses to start and names the key.** It never guesses.
