# journal_intelligence

> Sub-engine of the **Accounting Engine**. Canonical definition: [`docs/SUB_ENGINE_RESPONSIBILITIES.md`](../../../../docs/SUB_ENGINE_RESPONSIBILITIES.md). Deep spec: [`docs/ENGINE_3_ACCOUNTING_ENGINE_RULES.md`](../../../../docs/ENGINE_3_ACCOUNTING_ENGINE_RULES.md#86-journal_intelligence).
>
> **Phase 1 placeholder — no implementation.**

## Purpose

Design the journal structure — *is the final journal structurally correct?*

## Responsibility

Owns **debit/credit construction** and **the balance guarantee**: combining the approved accounting components, creating the journal structure, and ensuring **debit = credit** and accounting-equation balance.

## Input

The **Accounting Treatment Result** — Ledger Recommendation, Tax Treatment Recommendation and Accounting Period Treatment, combined by the parent engine.

## Output

**Journal Entry Recommendation** — debit accounts · credit accounts · amounts · reasoning · confidence.

## Boundary

**Can:** combine the approved accounting components · create the journal structure · ensure debit = credit · ensure accounting equation balance.

**Cannot:** post to Tally · change accounting rules · **calculate or interpret tax** · **select ledgers** — it consumes those decisions · force a balance by inserting a plug figure.

### Balance ≠ correctness

It guarantees **internal journal mathematical balance only.** Not accounting correctness, not tax correctness, not business correctness.

```text
Wrong ledger + balanced journal = still wrong
```

Correctness is judged by the Validation Engine. Balance is a property of the journal output itself — which is why only journal construction can guarantee it, and why guaranteeing it proves nothing about whether the entry is right.

## Decision Authority

**Owns.** Journal structure + balance.

**Cannot.** Decide tax or ledgers.

No other component may override this Result.

## Failure Behaviour

Return incomplete journal reasoning. An entry that will not balance is a doubt to be raised, never a rounding line to be invented.

## Future Notes

- The entry is deliberately system-neutral. Tally's representation is [`voucher_translator`](../../tally_engine/voucher_translator/)'s problem.
- It receives one combined artifact rather than three separate ones, so a component can never be silently missing at construction time.
