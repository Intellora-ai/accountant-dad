"""The Application Layer. `DATA_FLOW.md` §14, `SYSTEM_INVARIANTS.md` INV-4.

It owns creating the Transaction ID, starting engines, routing artifacts,
lifecycle, retrying engine execution, coordinating state transitions and
deciding a transaction is complete. It owns no decision, no artifact, no
confidence, no reasoning and no authority-table row.

The documents name this `src/services/`. It lives one segment deeper because
`pyproject.toml:18` ships only `src/accountant_dad`, and code the wheel cannot
see is code CI cannot judge (Law 44). The architectural name is unchanged.
"""
