"""Engine 5 — the Validation Engine. `ENGINE_5_VALIDATION_ENGINE_RULES.md`.

It decides whether an Accounting Decision may be posted, and emits exactly one
outbound artifact: the Validation Decision (`ENGINE_5:120`). At P3 the only
thing here is `stub.py`, which emits that artifact and validates nothing.

The directory name is the locked architectural identity, not a description of
what is inside it yet.
"""
