# Application Layer Invariants

> **Precedence level 3.** Subordinate to `SYSTEM_INVARIANTS.md`. Where these and a system invariant conflict, **the system invariant wins.**
>
> An invariant is **always true, at every moment, for every transaction.** Not a guideline, not a default.
>
> Every one below states **what it forbids** and **how it is checked** — an invariant nobody can check is a wish.

---

## AL-INV-1 — The Transaction ID is immutable

**Created once by the Application Layer. Never changed, never reissued, never reused.**

| | |
|---|---|
| **Forbids** | Any engine creating or modifying a Transaction ID · a correction receiving a new one · reuse after `Completed` |
| **Source** | `DATA_FLOW.md:615` — *"The Application Layer creates it. Engines consume it; they never create or modify it."* |
| **Checked by** | Conformance predicate: the Transaction ID on every artifact of a transaction is byte-identical. A correction's artifacts carry the **original** ID |
| **Why** | A wrong tax rate on a laptop purchase is still that purchase. Reversing and reposting does not make it a different business event |

---

## AL-INV-2 — Exactly one active state

**A Transaction ID is in exactly one state at any moment.**

| | |
|---|---|
| **Forbids** | Two states at once · no state at all · a state inferred from artifacts rather than recorded |
| **Source** | `DATA_FLOW.md §14` — *"Parallel transactions are allowed. Parallel states for one transaction are prohibited."* |
| **Checked by** | The state store permits exactly one row per Transaction ID. A transaction with zero or two states is a hard failure |
| **Note** | This invariant is what **forced Amendment 2**. `Approved With Warning` had no state to occupy, leaving such a transaction in *no* state |

---

## AL-INV-3 — State transitions are atomic

**A transition either completes fully or does not happen.**

| | |
|---|---|
| **Forbids** | Observing a half-applied transition · a crash leaving a transaction between states |
| **Source** | `DATA_FLOW.md §14` — *"Transitions are atomic."* |
| **Checked by** | Every transition is a single committed write. A crash mid-transition leaves the **previous** state intact |

---

## AL-INV-4 — Only the Application Layer changes workflow state

**No engine may read, write, observe or infer transaction state.**

| | |
|---|---|
| **Forbids** | An engine setting state · an engine branching on state · an engine waiting for a state · Engine 6 learning that a gate existed |
| **Source** | INV-4 — workflow is not an engine responsibility. `COMM_VALIDATION_ENGINE:71` — *"Engine 6 … never learns that a gate existed — which is exactly why it cannot accidentally skip one."* |
| **Checked by** | No engine's interface accepts or returns transaction state. Conformance: no engine module imports the state store |

---

## AL-INV-5 — Engines never call each other

**Every artifact passes through the Application Layer.**

| | |
|---|---|
| **Forbids** | Engine 2 calling Engine 3 · any engine holding another's address · any direct engine-to-engine arrow |
| **Source** | INV-4 — routing artifacts is the Application Layer's. `ENGINE_1..3` — *"Orchestrate the entire system"* is outside every engine |
| **Checked by** | Conformance: no engine module imports another engine. Component diagram has zero engine-to-engine arrows |
| **Why** | Two engines that can call each other can form a cycle nobody declared, and a decision could reach Execution without Validation |

---

## AL-INV-6 — No stage is skipped

**No decision reaches an external system without a Validation Decision approving it.**

| | |
|---|---|
| **Forbids** | Execution without Validation, however obvious the entry · bypassing Understanding for a "simple" document · fast paths of any kind |
| **Source** | `DATA_FLOW.md:283` — *"No stage may be bypassed … however obvious it appears."* `COMM_VALIDATION_ENGINE:65` — *"Engine 6 may never bypass Engine 5."* |
| **Checked by** | Every transition is validated against the allowed-transitions table. A disallowed transition is rejected, not logged and permitted |

---

## AL-INV-7 — Artifacts are immutable once produced

**The Application Layer never modifies an artifact. Correction means a new version.**

| | |
|---|---|
| **Forbids** | Editing an artifact in flight · annotating it while routing · repairing a malformed one · deleting one |
| **Source** | INV-4 — the Application Layer never owns any artifact. Standing rule — *"Artifacts are immutable after creation. Correction means a new version, never an edit."* |
| **Checked by** | Conformance predicate `artifacts_immutable`. The Application Layer's artifact handling is read-and-forward only |

---

## AL-INV-8 — The Brain never orchestrates

**The Brain provides knowledge. It never routes, sequences, retries, holds state or decides.**

| | |
|---|---|
| **Forbids** | The Brain observing workflow · being asked what to do next · returning a decision, treatment, approval, ledger, rate or instruction · the Application Layer querying the Brain |
| **Source** | INV-12 · `src/brain/README.md` — *"It is not an engine. It is not a decision maker … it never routes, orchestrates or sequences anything."* |
| **Checked by** | No arrow exists between `src/services/` and `src/brain/` in the component diagram. Conformance: `src/services/` never imports `src/brain/` |

---

## AL-INV-9 — `WaitingForApproval` is entered only by `Approved With Warning`

⚠️ **Depends on Amendment 2 — PROPOSED, not approved.**

| | |
|---|---|
| **Forbids** | Entering on `Approved` · on `Clarification Required` · on `Rejected` · any engine entering or leaving it · leaving it by any route except `release_waiting_for_approval()` |
| **Source** | `COMM_VALIDATION_ENGINE:61`, `:69` · `ENGINE_6:147` · `DATA_FLOW:283` |
| **Checked by** | The transition guard reads the Validation Decision status and permits this transition on exactly one value |
| **If Amendment 2 is rejected** | This invariant is void, and `Approved With Warning` must be removed from the architecture — the only other option you offered |

---

## AL-INV-10 — Engine failure is not an artifact

**An engine that cannot complete produces nothing. Never a partial artifact.**

| | |
|---|---|
| **Forbids** | Fabricating output to keep the pipeline moving · continuing with partial reasoning · persisting a half-built artifact · inferring a missing field |
| **Source** | INV-4 — *"Engine failure is not an artifact."* `ENGINE_6:260` |
| **Checked by** | A runtime failure records a failure event and **zero artifacts**. Restart begins from the last **completed** artifact |
| **Why** | *"A half-built artifact is more dangerous than none."* — `DATA_FLOW §14` |

---

## AL-INV-11 — Execution has no backward arrow

**Engine 6 never returns work to an earlier stage. It names the responsible stage; the Application Layer routes.**

| | |
|---|---|
| **Forbids** | Engine 6 sending work to Engine 5 · `error_handler` routing · any upstream call from Engine 6 |
| **Source** | `DATA_FLOW.md:285` · `COMM_VALIDATION_ENGINE:89` · `ENGINE_6:474` |
| **Checked by** | Conformance predicate `no_backward_transition_from_execution`. Engine 6's interface has no upstream call |

---

## AL-INV-12 — Retry never changes a conclusion

**Only runtime failures are retried. A business conclusion is never re-run to obtain a different answer.**

| | |
|---|---|
| **Forbids** | Retrying because confidence was low · re-running Understanding hoping for a better story · retrying a Validation `Rejected` · the Application Layer re-posting a voucher |
| **Source** | INV-4 — *"Business failures belong to sub-engines. Runtime failures belong to the Application Layer."* `COMM_EXECUTION_INTERNAL:131` |
| **Checked by** | Retry is permitted only for timeout, crash and unexpected exception. Every other class is non-retryable by construction |
| **Why** | Re-running reasoning that already succeeded could produce a **different conclusion from identical input**, destroying reproducibility. That is not a retry; it is a second opinion nobody asked for |

---

## AL-INV-13 — No state exists that is not in the state machine

**Your governing rule, made binding.**

> *"If a state is not in the locked state machine, it does not exist. Never invent execution states because they 'seem useful.'"*

| | |
|---|---|
| **Forbids** | `Cancelled` · `Paused` · `Queued` · `Retrying` · any hidden queue · any implicit waiting place |
| **Source** | Your ruling, 2026-08-03 |
| **Checked by** | The set of states in code equals the set in `DATA_FLOW.md §14` plus approved amendments — **exactly**, no more |
| **Consequence** | Cancellation does not exist. Retry is a **transition attribute**, never a state |

---

## AL-INV-14 — Configuration has no defaults

**Every required configuration value is supplied explicitly. A missing one is a startup failure.**

| | |
|---|---|
| **Forbids** | A default retry count · a default timeout · a fallback endpoint · any value chosen by the implementation |
| **Source** | `CLAUDE.md` Law 52 — everything measurable, nothing assumed. Your rule 10 — *"Never set a number I did not give you."* |
| **Checked by** | Startup validates every required key is present. Absent → refuse to start, name the key |
| **Why** | A default retry count is a number nobody chose, silently governing how many times a financial operation is attempted |

---

## Invariant coverage

| System invariant | Preserved by |
|---|---|
| INV-4 — Reasoning separate from workflow | AL-INV-4 · 5 · 7 · 10 · 12 |
| INV-9 — Identity ≠ intelligence | AL-INV-1 |
| INV-10 — One concept, one owner | AL-INV-4 · 5 · 7 |
| INV-12 — Knowledge shared, authority not | AL-INV-8 |
| Artifact immutability | AL-INV-7 |
| No skipping | AL-INV-6 |
| Atomicity | AL-INV-3 |

**No Application Layer invariant contradicts, weakens or reinterprets a system invariant.** Verified in `ARCHITECTURE_AUDIT.md`.
