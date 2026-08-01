# engines

> The six engines. **Phase 1 placeholder — no implementation.**

Each engine is one **cognitive stage**, not one technical layer. The split follows the order a competent accountant thinks in.

| # | Engine | The question it answers |
|---|---|---|
| 1 | [`input_engine`](input_engine/) | *What does this document actually say?* |
| 2 | [`understanding_engine`](understanding_engine/) | *What happened in the business?* |
| 3 | [`accounting_engine`](accounting_engine/) | *How should it be recorded?* |
| 4 | [`clarification_engine`](clarification_engine/) | *What do we still need to ask a human?* |
| 5 | [`validation_engine`](validation_engine/) | *Is this safe to post?* |
| 6 | [`tally_engine`](tally_engine/) | *Put it in the books, and record that we did.* |

## Flow

```text
Input → Understanding → Accounting Decision → Clarification (if required) → Validation → Tally Execution
```

Detail: [`docs/DATA_FLOW.md`](../../docs/DATA_FLOW.md).

## Structure rule

The tree is exactly three levels deep and stops there:

```text
engines/ → <engine>/ → <sub_engine>/ → README.md
```

No folders may be created inside an engine or a sub-engine. `models/`, `pipelines/`, `utils/`, `adapters/` and `configs/` are implementation decisions for later phases and are explicitly forbidden here.

## The four boundaries most likely to erode

`business_context` vs `company_understanding` · `risk_analysis` vs `risk_assessment` · `doubt_detection` vs `uncertainty_detection` · `ledger_intelligence` vs `journal_intelligence`

Each is separated by one sharp distinction, stated in [Ownership Collisions](../../docs/SUB_ENGINE_RESPONSIBILITIES.md#ownership-collisions).
