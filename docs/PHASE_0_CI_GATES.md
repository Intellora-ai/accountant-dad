# Phase 0 — GitHub CI Gates

> **Precedence level 3 — Engine Specifications.** The first phase of the MVP build.
>
> Parent: [`MVP_IMPLEMENTATION_BLUEPRINT.md`](MVP_IMPLEMENTATION_BLUEPRINT.md) · loop: [`MVP_BUILD_VERIFY_FIX.md`](MVP_BUILD_VERIFY_FIX.md) · reporting: [`PHASE_REPORT_TEMPLATE.md`](PHASE_REPORT_TEMPLATE.md)
>
> ## ⛔ Nothing else is built until this phase is green.

---

## Why this phase exists

`CLAUDE.md` **Law 44**: *a result exists only if GitHub CI produced it. A local pass is exploration, not evidence.*

That law has a consequence the blueprint states as a **build freeze**: **code written before the gates exist cannot be verified.** It cannot be called done. It accumulates as unverified work — the exact debt this whole framework was written to prevent.

**So the gates come first. Before the golden set, before the schemas, before any engine.**

---

## The transform

**Law 53** — *transform the hard problem into an equivalent easier one; never attack it directly.*

| | |
|---|---|
| **Hard** | *"Build CI for code that does not exist yet."* Produces a workflow nobody has watched do anything. |
| **Equivalent, easier** | **Build CI that gates the 31 documents that already exist.** |

Real work today. Catches real defects. And it **proves the harness before any product code depends on it.**

The code stages are added now as no-ops and fill in as P2–P6 arrive. The pipeline shape is right from the first commit.

---

## What gets built

```
.github/workflows/gate.yml       the workflow
tools/check_docs.py              link · header · naming · structure checks
tests/test_gate_is_real.py       the red-proof
pyproject.toml                   minimum tooling config   ⚠️ see Decisions
```

### Five stages

| Stage | Real today | Checks |
|---|---|---|
| **docs** | ✅ **fully** | Every relative link resolves · every doc carries a precedence header · no stale artifact names at artifact level (`Validation Verdict`, `Posting Result`) · 6 engines · 39 sub-engines · 0 directories deeper than three · 0 non-README files under `src/` |
| **lint** | no-op → real at P2 | `ruff` |
| **typecheck** | no-op → real at P2 | `mypy` |
| **test** | ✅ minimal | `pytest` |
| **conformance** | placeholder → real at P2 | the predicate suite from [`MVP_BUILD_VERIFY_FIX.md`](MVP_BUILD_VERIFY_FIX.md) §4.1 |

**The `docs` stage is a genuine gate from day one.** It automates the six structural checks that have been run by hand throughout the specification work — checks which, under Law 44, **have not counted as verification at all until they run in CI.**

---

## Done when the gate goes RED

> **A gate nobody has watched fail is a badge, not a gate.**

The proof is mandatory and it is the whole point of the phase:

```
1.  push a deliberately broken link   →  workflow MUST go red    →  record run URL
2.  revert                            →  workflow MUST go green  →  record run URL
3.  both URLs recorded in the P0 report
```

A workflow that has only ever been green is indistinguishable from a workflow that does nothing.

### Also required

- Triggers on **push** and **pull_request**
- **Branch protection on `main`** — green required to merge
- P0 report written per [`PHASE_REPORT_TEMPLATE.md`](PHASE_REPORT_TEMPLATE.md), **before** the commit (Law 51)

---

## Definition of done

| # | Condition |
|---|---|
| 1 | Workflow file valid, triggers on push and PR |
| 2 | All five stages present; `docs` and `test` genuinely green |
| 3 | **Deliberate break produced a RED run — URL recorded** |
| 4 | **Revert produced a GREEN run — URL recorded** |
| 5 | Branch protection blocks merge on red |
| 6 | `docs` stage catches all six structural check types |
| 7 | **No product code added** — the build freeze held |
| 8 | P0 report written before the commit |

---

## Blockers

| Blocker | State |
|---|---|
| **GitHub repository** | ❌ **No remote exists.** No repo, no Actions, no results. |
| `pyproject.toml` decision | ⬜ Awaiting — see below |
| Repository name and visibility | ⬜ Awaiting |

---

## Decisions required — not taken unilaterally (§E.8)

### 1. `pyproject.toml` reverses a Phase 1 decision

It was **explicitly rejected in Phase 1**. But CI cannot invoke `ruff`, `mypy` or `pytest` without some configuration.

| Option | Consequence |
|---|---|
| **Add it now** | Tooling config, not product code. The build freeze is about engines and artifacts, not about the ability to run a linter. |
| **Keep the tree README-only** | The `docs` stage becomes the only gate until P2. Still a real gate — it just cannot check code that does not exist yet. |

**This is a reversal of a decision the user made, so the user makes it.**

### 2. Repository name and visibility

`accountant dad` contains a space; GitHub needs a slug. Visibility presumably private.

---

## What Phase 0 does NOT do

No engine. No sub-engine. No schema. No artifact. No pipeline. No LLM. No Tally. **No product code of any kind.**

> **P0 builds the thing that can say *no*.**
> **P1 builds the thing that can say *wrong*.**

Neither produces product. That is deliberate, and it is the order that makes every number after them mean something.

---

## Next

**Phase 1 — Human Ceiling and Golden Set.** Separately blocked on sign-off of the 6 definitions, the 9 finish conditions and the absolute floor, plus two accountants' time. Phase 1 writes no code either.
