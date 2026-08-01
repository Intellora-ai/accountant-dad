# services

> **Reserved directory. Phase 1 placeholder — no implementation.**

## Purpose

Shared infrastructure concerns that are not part of any engine's reasoning.

## What will belong here

Cross-cutting technical capability that engines use but none of them owns.

## What must not belong here

- **Any engine responsibility.** Nothing here may read, understand, decide, ask, validate or post.
- Accounting, tax or business logic of any kind.
- Anything that would let an engine reach past its boundary by calling into this directory.

## The risk this directory carries

A `services/` folder is where architectures usually erode. Logic that "does not fit anywhere" gets placed here, and the ownership stated in [`docs/ENGINE_RESPONSIBILITIES.md`](../../docs/ENGINE_RESPONSIBILITIES.md) quietly stops being true.

If something does not fit in an engine, that is a signal the architecture needs a decision — not a signal to put it here. **Stop and ask.**

## Status

Empty by design.
