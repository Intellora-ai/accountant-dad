# tally_connector

> Sub-engine of the **Execution Engine**. Canonical definition: [`docs/SUB_ENGINE_RESPONSIBILITIES.md`](../../../../docs/SUB_ENGINE_RESPONSIBILITIES.md). Deep spec: [`docs/ENGINE_6_EXECUTION_ENGINE_RULES.md`](../../../../docs/ENGINE_6_EXECUTION_ENGINE_RULES.md#92-tally_connector).
>
> **Phase 1 placeholder — no implementation.**

## Purpose

The connection to an external system is its own concern, with its own failures.

## Responsibility

Owns **connection, transmission and acknowledgement** — external connections, authentication, API communication, connector sessions, session and company selection, and availability.

## Name and responsibility

**Architecturally this is the destination connector.** Its responsibility covers all external accounting systems, not Tally alone — Zoho, Busy, SAP, QuickBooks, portals and exports all connect here. **The locked folder name is retained: identities are stable, responsibilities are not.** Same pattern as Engine 4's three.

## Input

The **Translated Voucher**, and connection configuration.

## Output

The **Connection Result** — a working channel, connection state, and transport-level results.

## Boundary

**Can:** connect · authenticate · send voucher · receive responses · disconnect safely.

**Cannot:** modify voucher · inspect or interpret a payload passing through it · change accounting · **retry endlessly** · skip authentication · ignore connection failures · **reason**. Cannot judge whether a response means success — that is [`response_processor`](../response_processor/).

## Failure Behaviour

**Report failure · hand control to [`error_handler`](../error_handler/) · preserve execution state.**

## Future Notes

- Tally is frequently a machine on someone's desk. Unavailability is a normal operating state, not an exception, and the design should treat it that way.
- Selecting the wrong company would post correct entries into the wrong books. Company selection belongs here and deserves to be explicit.
