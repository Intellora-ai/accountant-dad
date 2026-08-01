# response_processor

> Sub-engine of the **Execution Engine**. Canonical definition: [`docs/SUB_ENGINE_RESPONSIBILITIES.md`](../../../../docs/SUB_ENGINE_RESPONSIBILITIES.md). Deep spec: [`docs/ENGINE_6_EXECUTION_ENGINE_RULES.md`](../../../../docs/ENGINE_6_EXECUTION_ENGINE_RULES.md#94-response_processor).
>
> **Phase 1 placeholder — no implementation.**

## Purpose

*"The system replied"* and *"the entry is in the books"* are not the same statement.

## Responsibility

Owns **success/failure interpretation** — turning what the destination returned into one definite outcome (posted, rejected, or partial), with the identifiers it assigned.

## Input

The **External Response**, and the corresponding post attempts.

## Output

The **Processed Execution Result** — outcome, external transaction identifiers, and the raw response it was derived from.

## Boundary

**Can:** interpret response codes · extract transaction IDs · record posting status · detect successful execution.

**Cannot:** rewrite responses · ignore failures · retry or resubmit · modify accounting decisions · **increase accounting confidence** · change business decisions. Cannot classify or route a failure — that is [`error_handler`](../error_handler/).

## Failure Behaviour

**Unknown responses remain visible. Never assume success. Never invent external IDs.** An ambiguous or absent response is never read as success.

## Future Notes

- The raw response is retained alongside the interpretation so that a wrong interpretation can be found later. This matters more here than almost anywhere else in the system.
- **A partial post is a business outcome, not a partial artifact.** It is fully described in a complete Execution Result — most damaging to mis-read, and a first-class result rather than a variant of failure.
