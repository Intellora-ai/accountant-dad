# tally_connector

> Sub-engine of the **Tally Engine**. Canonical definition: [`docs/SUB_ENGINE_RESPONSIBILITIES.md`](../../../../docs/SUB_ENGINE_RESPONSIBILITIES.md).
>
> **Phase 1 placeholder — no implementation.**

## Purpose

The connection to an external system is its own concern, with its own failures.

## Responsibility

Owns the connection to Tally — transport, session, company selection, and availability.

## Input

Connection configuration, and payloads to be transmitted.

## Output

A working channel, connection state, and transport-level results.

## Boundary

Cannot inspect, interpret or modify a payload passing through it. Cannot decide whether to retry. Cannot judge whether a Tally response means success — that is [`response_processor`](../response_processor/).

## Future Notes

- Tally is frequently a machine on someone's desk. Unavailability is a normal operating state, not an exception, and the design should treat it that way.
- Selecting the wrong company would post correct entries into the wrong books. Company selection belongs here and deserves to be explicit.
