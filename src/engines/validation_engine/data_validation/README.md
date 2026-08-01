# data_validation

> Sub-engine of the **Validation Engine**. Canonical definition: [`docs/SUB_ENGINE_RESPONSIBILITIES.md`](../../../../docs/SUB_ENGINE_RESPONSIBILITIES.md). Deep spec: [`docs/ENGINE_5_VALIDATION_ENGINE_RULES.md`](../../../../docs/ENGINE_5_VALIDATION_ENGINE_RULES.md#101-data_validation).
>
> **Phase 1 placeholder — no implementation.**

## Purpose

A perfectly reasoned entry built on broken data is still broken.

## Responsibility

Owns **data validation** — whether every required input artifact exists, is complete, internally consistent, version-correct and structurally valid: required fields present, dates within permissible range and sequence, totals reconciling to their lines, every referenced master actually existing.

**Owns the closed-period gate.** A closed accounting period, a statutory lock or an exceeded authorisation limit is a **Critical** finding raised here, *before execution begins* — [`docs/SYSTEM_INVARIANTS.md` INV-8](../../../../docs/SYSTEM_INVARIANTS.md#inv-8--permission-to-execute-is-decided-before-execution).

## Input

The Accounting Decision · the Clarification Request · reference artifacts: the Business Understanding Object, the Confidence Report within the Document Evidence Object, and Company Context including the company's master data.

## Output

The **Data Validation Result** — completeness · missing artifacts · version compatibility · traceability status · confidence.

## Boundary

**Can:** verify · inspect · compare · report.

**Cannot:** edit artifacts · create artifacts · infer missing information · modify accounting · correct, complete or normalise any data. Cannot judge whether the accounting treatment is right. Cannot lower a requirement because the data cannot meet it.

## Failure Behaviour

**If required data is missing, report every missing component and stop further validation.**

This is the **only** sub-engine permitted to short-circuit — there is nothing to validate against absent artifacts. It reports *all* missing components, never the first one found.

## Future Notes

- This is where a discrepancy faithfully carried from [`parser`](../../input_engine/parser/) is finally adjudicated — the whole pipeline preserved it for this moment.
- A data defect a human could resolve is routed to Clarification, not to Input. The routing rule is in [`docs/DATA_FLOW.md`](../../../../docs/DATA_FLOW.md#44-validation-returns-work-it-never-passes-it-on).
- Permission and correctness are different questions. Engine 3 decides what is correct; this decides whether the books will accept it at all.
