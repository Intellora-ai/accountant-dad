# models

> **Defined as of Phase 0.** **Phase 1 placeholder — no implementation.**

## Purpose

**Canonical domain models and schemas** — the shape of every artifact and every domain concept the system reasons about.

Governed by [`docs/SYSTEM_INVARIANTS.md` INV-6](../../docs/SYSTEM_INVARIANTS.md#inv-6--every-canonical-artifact-has-a-specification-level-schema): **schemas are architecture, not implementation.**

## What will belong here

- The **canonical artifacts**: Document Evidence Object · Business Understanding Object · Accounting Decision · Clarification Request · Validation Decision · Execution Result.
- The **identity envelope** every artifact carries: Artifact ID · Version · Parent Artifact Version(s) · Transaction ID.
- The **provenance envelope** every fact carries: Source Type · Source ID · Evidence Reference · Timestamp · Confidence · Corroborated.
- Domain concepts more than one engine must speak about in the same terms.

Each schema defines: identity fields · required fields · optional fields · relationships · ownership · versioning · Transaction ID reference · evidence references · confidence representation.

**No database decisions. No programming language. Only canonical structure.**

> **Two independent engineers must build identical artifacts from the specification.**

## What must not belong here

- Business logic of any kind. A model carries no judgement.
- Shapes internal to a single engine.

## Status

Empty by design. Written after Engines 5 and 6 are locked, when every artifact exists.
