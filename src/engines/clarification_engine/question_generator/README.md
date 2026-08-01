# question_generator

> Sub-engine of the **Clarification Engine**. Canonical definition: [`docs/SUB_ENGINE_RESPONSIBILITIES.md`](../../../../docs/SUB_ENGINE_RESPONSIBILITIES.md). Deep spec: [`docs/ENGINE_4_CLARIFICATION_ENGINE_RULES.md`](../../../../docs/ENGINE_4_CLARIFICATION_ENGINE_RULES.md#106-question_generator).
>
> **Phase 1 placeholder — no implementation.**

## Purpose

Construct the canonical Clarification Request.

## Responsibility

Owns **Clarification Request creation**.

## Name and responsibility

It formulates what is asked. The Clarification Request *is* what Phase 1 called the Question Set, in structured form — what is missing, why it matters, what is needed. **Generating the question is generating the request.**

## Input

Outputs from **every previous Clarification sub-engine**.

## Output

The **Clarification Request**.

```text
Clarification Request
├── Clarification ID · Related Decision ID · Related Artifact Version
├── Missing Information · Detected Conflicts
├── Required Clarification · Reason Clarification Is Required
├── Affected Decision · Priority
├── Supporting Evidence References
├── Clarification Confidence
└── Status
```

## Boundary

**Can:** assemble clarification · merge clarification components · preserve evidence references.

**Cannot:** invent clarification · modify upstream decisions · hide uncertainty · rewrite reasoning.

> **`question_generator` creates the artifact. The Clarification Engine owns it.**

It does not become an independent owner. Assembly is not permission to edit.

## Failure Behaviour

**Produces an incomplete Clarification Request while preserving every unresolved issue.** An incomplete request that names what it could not determine is correct output; a complete-looking request that dropped an issue is not.

## Future Notes

- **Related Artifact Version** is what makes a stale request detectable. A request raised against decision `v3` is obsolete the moment `v4` exists.
- Two consumers read this artifact — the external actor who must act on it, and the Validation Engine, which reads it to learn whether unresolved uncertainty exists. Design it for both.
