# audit_logger

> Sub-engine of the **Tally Engine**. Canonical definition: [`docs/SUB_ENGINE_RESPONSIBILITIES.md`](../../../../docs/SUB_ENGINE_RESPONSIBILITIES.md).
>
> **Phase 1 placeholder — no implementation.**

## Purpose

The books must be defensible, which means the trail must be complete.

## Responsibility

Owns the immutable record of every posting attempt — what was sent, when, on which decision's authority, and what came back.

## Input

Voucher payloads, post attempts, Posting Results, and Classified Errors.

## Output

The **Audit Record**: permanent, append-only, and linked to the decision that authorised it.

## Boundary

Cannot alter or delete a record once written. Cannot omit failures, retries or partial outcomes. Cannot summarise away detail that would be needed to reconstruct what happened.

## Future Notes

- Append-only is a property of the design, not a convention to be observed. If a record can be updated, it is not an audit record.
- The link back to the authorising decision is what makes the whole pipeline reconstructible from an entry in the books — the single most valuable property this component provides.
