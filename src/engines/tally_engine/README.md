# Tally Engine

> Engine 6 of 6. Canonical definition: [`docs/ENGINE_RESPONSIBILITIES.md`](../../../docs/ENGINE_RESPONSIBILITIES.md).
>
> **Phase 1 placeholder — no implementation.**

## Purpose

*Put it in the books, and record that we did.*

Execution against an external system fails in its own ways — the connection drops, Tally rejects a voucher, a post half-succeeds. Those failures must never be confused with accounting errors, so this engine owns no reasoning at all.

## Responsibility

Execute the approved decision against Tally and record the truth of what happened.

Sub-engines:

| Sub-engine | Owns |
|---|---|
| [`voucher_translator`](voucher_translator/) | Decision → Tally voucher |
| [`tally_connector`](tally_connector/) | The connection |
| [`posting_manager`](posting_manager/) | The act of posting |
| [`response_processor`](response_processor/) | What Tally actually said |
| [`error_handler`](error_handler/) | Classifying and routing failures |
| [`audit_logger`](audit_logger/) | The immutable record |

## Input

**Approved Accounting Decision** — and nothing that has not been approved.

## Output

- **Posting Result** — posted, rejected or partial, with Tally's identifiers.
- **Classified Error** — where posting failed, its category and the stage that must act.
- **Audit Record** — the permanent, immutable account of the attempt and its outcome.

## Boundary

**Cannot reason.** Cannot interpret or judge the transaction. Cannot alter the accounting meaning of what it was given. Cannot supply a missing value — missing data is an error, not a gap to fill. Cannot decide whether posting should happen. Cannot correct a rejected voucher and resubmit it. Cannot alter, delete or omit an audit record.

## Future Notes

- This is the only engine that touches anything outside the system, and the only one whose failures are not accounting failures. Keeping those two facts aligned is the reason it holds no reasoning.
- Tally's XML/HTTP interface and its version differences are entirely [`tally_connector`](tally_connector/) and [`voucher_translator`](voucher_translator/)'s concern; no other engine should ever learn about them.
