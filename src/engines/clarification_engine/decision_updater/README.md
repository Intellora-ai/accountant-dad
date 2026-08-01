# decision_updater

> Sub-engine of the **Clarification Engine**. Canonical definition: [`docs/SUB_ENGINE_RESPONSIBILITIES.md`](../../../../docs/SUB_ENGINE_RESPONSIBILITIES.md). Deep spec: [`docs/ENGINE_4_CLARIFICATION_ENGINE_RULES.md`](../../../../docs/ENGINE_4_CLARIFICATION_ENGINE_RULES.md#107-decision_updater).
>
> **Phase 1 placeholder — no implementation.**

## Purpose

Track the lifecycle of every clarification request.

Clarification is **not complete when a request is created.** It is complete only when the required information has been received and the responsible upstream engine has produced a new artifact version.

## Responsibility

Owns **clarification lifecycle · clarification status · clarification history**.

## Name and responsibility

It is the component that knows the relationship between a clarification and the **state of the decision**. In Phase 1 it carried answers back so the decision could be remade; it now links each clarification to the decision version it was raised against, and marks it obsolete when a newer version supersedes it. Version-and-state tracking in both eras.

## Input

The **Clarification Request**.

## Output

**Clarification Status Result** — current status · timestamps · related artifact versions · resolution history · audit trail.

## Boundary

**Can:** track progress · maintain history · link clarification to artifact versions.

**Cannot: resolve clarification** · modify decisions · approve execution.

### The lifecycle

```text
Created ──► Waiting for Information ──► Information Received ──► Closed
   │                  │                          │
   └──────────────────┴──────────────────────────┴──────► Obsolete
```

| State | Trigger |
|---|---|
| **Created** | `question_generator` assembled the Request |
| **Waiting for Information** | Request handed to the external actor |
| **Information Received** | External actor supplied a Clarification Answer — **recorded, never interpreted** |
| **Obsolete** | An upstream engine emitted a version newer than Related Artifact Version |
| **Closed** | A new artifact version no longer carries the uncertainty that caused the request |

`Closed` and `Obsolete` are terminal; `Obsolete` is reachable from any state. Nothing goes from `Created` straight to `Closed` — closure requires a new artifact version.

**It owns every transition but no resolution.** Resolution is an upstream engine emitting a new artifact version. Owning the status is not owning the outcome.

## Failure Behaviour

**Preserve complete audit history even if clarification remains unresolved.** History is never trimmed because a request went nowhere.

## Future Notes

- **Obsolete ≠ Closed.** Collapsing the two would hide that a question went unanswered — the most valuable signal this component produces.
- Staleness is structural, not noticed: the version chain makes it computable, so no engine has to report back for a request to become obsolete.
