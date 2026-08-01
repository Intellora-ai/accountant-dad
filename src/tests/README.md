# tests

> **Reserved directory. Phase 1 placeholder — no implementation.**

## Purpose

Verification.

## What will belong here

Tests for the engines and their boundaries, once implementation begins.

## What is most worth testing

The boundaries. Correct outputs are the easy half; the properties that make this system trustworthy are all prohibitions, and prohibitions are what erode silently:

- The Input Engine made no accounting decision.
- The Understanding Engine's story contains no accounting vocabulary.
- The Accounting Engine reached Tally never, and the user never.
- A doubt was never resolved by a default.
- The Validation Engine amended nothing it judged.
- Nothing reached Tally without an approving verdict.
- The Tally Engine supplied no missing value.
- No audit record was altered, and no failure went unlogged.

Each of these corresponds to a "cannot" in [`docs/SYSTEM_BOUNDARIES.md`](../../docs/SYSTEM_BOUNDARIES.md).

## Status

Empty by design. There is nothing to test yet.
