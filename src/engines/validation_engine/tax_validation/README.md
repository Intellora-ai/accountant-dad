# tax_validation

> Sub-engine of the **Validation Engine**. Canonical definition: [`docs/SUB_ENGINE_RESPONSIBILITIES.md`](../../../../docs/SUB_ENGINE_RESPONSIBILITIES.md). Deep spec: [`docs/ENGINE_5_VALIDATION_ENGINE_RULES.md`](../../../../docs/ENGINE_5_VALIDATION_ENGINE_RULES.md#103-tax_validation).
>
> **Phase 1 placeholder — no implementation.**

## Purpose

Tax errors are the ones that come back years later.

## Responsibility

Owns **tax validation** — whether the tax treatment is compliant and internally consistent: rate against classification, place of supply against parties, ITC eligibility against the stated basis, TDS against applicability.

## Input

The Accounting Decision — its tax treatment and tax lines, the party and item facts, the company's tax profile · the Data Validation Result.

## Output

The **Tax Validation Result** — GST findings · tax inconsistencies · missing tax information · confidence.

## Boundary

**Can:** validate · compare tax treatment · report.

**Cannot:** calculate new tax · rewrite tax treatment · recompute or change a tax amount · select a different treatment · file or report anything.

## Failure Behaviour

**Unknown tax treatment remains unknown. Never invent tax interpretation.** Where the basis for a treatment is absent, that absence *is* the finding.

## Future Notes

- The specific tax domains this validates — HSN/SAC, place of supply, reverse charge, ITC eligibility, blocked credits, TDS, TCS, e-invoicing, e-way bills, GSTR reconciliation — are named as expected scope, not measured scope. The Reality Probe that was to establish them was deferred; recorded in [`docs/FORWARD_DEPENDENCY_INVENTORY.md`](../../../../docs/FORWARD_DEPENDENCY_INVENTORY.md).
- Internal consistency is checkable now; full statutory compliance is a larger problem and should be scoped deliberately rather than assumed.
- A tax finding usually carries higher severity than an equivalent accounting one, because the cost of being wrong lands outside the business.
