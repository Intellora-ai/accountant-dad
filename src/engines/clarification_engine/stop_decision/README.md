# stop_decision

> Sub-engine of the **Clarification Engine**. Canonical definition: [`docs/SUB_ENGINE_RESPONSIBILITIES.md`](../../../../docs/SUB_ENGINE_RESPONSIBILITIES.md).
>
> **Phase 1 placeholder — no implementation.**

## Purpose

Asking forever is its own failure mode.

## Responsibility

Owns the judgement of when questioning ends — because clarity is sufficient, because further questions would not change the decision, or because the human cannot supply what is needed.

## Input

The state of the material uncertainties, the answers received, and the questions already asked.

## Output

The **Clarification Outcome** — continue or stop, the reason, and any uncertainty that remains unresolved.

## Boundary

Cannot stop by declaring the decision correct or safe — it concludes only that questioning is complete. Cannot conceal an unresolved uncertainty when stopping. Cannot continue questioning where no question would change the outcome.

## Future Notes

- Stopping with uncertainty still open is a legitimate and expected outcome. What it must never be is a silent one — the remaining uncertainty goes to Validation, which may well flag it for a human.
- The three stopping grounds are genuinely different and should stay distinguishable in the output; "the human could not answer" is a very different signal from "we have enough".
