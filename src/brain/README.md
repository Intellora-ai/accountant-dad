# brain

> **Reserved directory. Phase 1 placeholder — no implementation.**

## Status: role not yet defined

This directory is part of the agreed repository structure, but its responsibility has **not** been defined by the architecture. Nothing in [`docs/`](../../docs/) assigns it a mission, inputs, outputs or boundary.

## Before anything is placed here

Its role must be defined first, in the documentation, and agreed. Specifically:

- What problem does it own that no engine owns?
- What does it receive, and from whom?
- What does it produce, and for whom?
- What is it forbidden to do?

**Do not resolve this by writing code here.** An undefined component that acquires responsibilities by accident is exactly how ownership becomes unclear — which [`docs/SYSTEM_BOUNDARIES.md`](../../docs/SYSTEM_BOUNDARIES.md) forbids.

If work appears to belong here: **stop and ask.**

## What must not happen here

No engine responsibility may be moved into this directory. The six engines own the reasoning; nothing here may decide, validate or post on their behalf.
