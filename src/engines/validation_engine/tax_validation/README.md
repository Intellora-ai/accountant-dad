# tax_validation

> Sub-engine of the **Validation Engine**. Canonical definition: [`docs/SUB_ENGINE_RESPONSIBILITIES.md`](../../../../docs/SUB_ENGINE_RESPONSIBILITIES.md).
>
> **Phase 1 placeholder — no implementation.**

## Purpose

Tax errors are the ones that come back years later.

## Responsibility

Owns the judgement of whether the tax treatment is compliant and internally consistent — rate against classification, place of supply against parties, ITC eligibility against the stated basis, TDS against applicability.

## Input

The tax treatment and tax lines from the decision, the party and item facts, and the company's tax profile.

## Output

A tax verdict with findings.

## Boundary

Cannot recompute or change a tax amount. Cannot select a different treatment. Cannot file or report anything.

## Future Notes

- Internal consistency is checkable now; full statutory compliance is a larger problem and should be scoped deliberately rather than assumed.
- A tax finding usually carries higher severity than an equivalent accounting one, because the cost of being wrong lands outside the business.
