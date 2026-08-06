# Technology Stack — the project default

**Status: LOCKED.** Approved by the user, 2026-08-05, as a project invariant.

> **One primary tool per capability.** Optimised for accuracy · determinism ·
> maintainability · replaceability · simplicity — **not** for the largest number of
> tools.
>
> **No component is replaced without measurable evidence** that another is objectively
> better on accuracy, latency, determinism, maintainability or reliability. "Better" here
> means a number with a unit (Law 52), not a preference.

Every entry is `NOT INSTALLED` until its engine's phase is reached and its twelve
implementation checks pass. Listing a tool here is a decision, not an installation.

---

## Engine 1 — Input Engine

Image preprocessing · OCR · layout detection · table extraction · PDF parsing ·
confidence estimation.

| Tool | Capability |
|---|---|
| OpenCV | deskew, denoise, crop, contrast, format normalisation |
| PaddleOCR | **the** OCR. Text extraction with per-region confidence |
| Docling | document parsing and structure |
| PyMuPDF | PDF text layer — no OCR needed when a PDF carries real text |
| Microsoft Table Transformer | table structure detection |
| Gemini 2.5 Flash Vision | **fallback only** — and it has **no trigger**. See the note below |

**Explicitly NOT approved** — do not install without a later, explicit approval:
`Tesseract · EasyOCR · Camelot · Tabula · ImageMagick · Unstructured`

> **The Gemini fallback has no trigger, and a confidence threshold may not become one.**
> Revised by Amendment 8. This previously read *"the threshold that triggers the Gemini
> fallback is not set ... a number nobody has given"*, which framed the blocker as a
> missing NUMBER. It is not: Decision **A7** and `MEASUREMENT_FRAMEWORK.md` §10 hold that
> confidence gates NOTHING until the separation test passes, so setting that number would
> be forbidden even if the owner supplied one today.
>
> What the trigger should be instead is **undecided and needs the owner** — it is a
> routing decision, not a measurement. Until it exists the fallback path cannot be
> implemented, only stubbed. **No number is recorded here, because no number is the
> blocker.**

## Engine 2 — Understanding Engine

| Tool | Capability |
|---|---|
| Gemini 2.5 Flash | the reasoning model |
| Pydantic AI | structured, typed model output |
| JSON Schema | output contract |
| Guardrails AI | output constraint enforcement |
| spaCy | linguistic processing |
| OpenRouter | **fallback only** |

## Engine 3 — Accounting Engine

**NO LLM. NO AI REASONING. Pure deterministic accounting.**

This is the strongest constraint in the stack and it is deliberate: the engine that
decides the entry must be reproducible, inspectable and defensible. A model that
reasons differently on two runs cannot be any of those.

| Tool | Capability |
|---|---|
| Python + `Decimal` | arithmetic. Never `float` — see `confidence.py` on why |
| rule-engine | rule evaluation |
| jsonlogic | portable rule representation |
| NetworkX | dependency and relationship graphs |
| Pydantic | artifact schemas |

Knowledge consumed: GST · ICAI · Companies Act · Income Tax · HSN · SAC —
from `Accounting_Brain/`, where every claim carries a verified citation.

## Engine 4 — Clarification Engine

| Tool | Capability |
|---|---|
| Gemini Flash | question generation |
| BAAI BGE Large | embeddings |
| FastEmbed | retrieval |
| Qdrant | vector database |

**Explicitly NOT approved:** `Chroma` · `FAISS` (local experiments only).

## Engine 5 — Validation Engine

| Tool | Capability |
|---|---|
| Great Expectations | data expectations |
| DeepDiff | structural comparison |
| RapidFuzz | fuzzy matching |
| NetworkX | graph checks |
| pytest | assertion harness |
| Pydantic | schema validation |

> **Validation MUST be deterministic. An LLM may EXPLAIN a failure. An LLM never
> decides correctness.** This mirrors `ENGINE_5`: validation only validates, and a
> defect is reported, never fixed.

## Engine 6 — Execution Engine

| Tool | Capability |
|---|---|
| requests / httpx | HTTP transport |
| xmltodict / lxml | XML |
| asyncio | concurrency |
| Jinja2 | voucher templating |

Protocols: Tally XML · HTTP · XML.

## Global

| Capability | Tool |
|---|---|
| Embedding | BAAI BGE Large |
| Reranker | bge-reranker |
| Vector DB | Qdrant |
| OCR | PaddleOCR |
| Parser | Docling |
| Vision | Gemini Flash Vision |
| LLM | Gemini Flash |
| Observability | OpenTelemetry · Langfuse |
| Validation | JSON Schema · Pydantic · Guardrails |
| Workflow | asyncio |

---

## Blockers — external, and real

| Blocker | Kind | Blocks |
|---|---|---|
| Gemini API key | credential | Engines 1 (fallback), 2, 4 |
| Qdrant instance | infrastructure — a server, not a pip install | Engine 4 |
| Gemini fallback trigger | **undecided** — a routing decision, not a number. The one proposed was a confidence threshold, which A7 forbids | Engine 1 fallback |
| Tally instance | infrastructure — TallyPrime is Windows | Engine 6 |

## Integration — a tool is not integrated until all twelve pass

```
1 installed          5 abstraction layer   9  failure handling
2 version pinned     6 dependency docs     10 benchmarks where applicable
3 compatible         7 install docs        11 imports verified
4 licence verified   8 health check        12 smoke + integration test
```

Per engine: `TOOLCHAIN.md · DEPENDENCIES.md · INSTALLATION.md · HEALTHCHECK.md ·
TEST_PLAN.md`, each recording why chosen, why alternatives were rejected, licence,
version, update strategy, known limitations, performance characteristics, failure modes
and replacement strategy.

## Rules

- **Never silently swap a technology.** A swap is a documented decision with a number.
- **Never add a second tool for a capability that already has one.**
- **Never add a convenience library without measurable benefit.**
- **Every addition carries a documented reason.**

## Why this is not yet in `requirements-ci.txt`

`requirements-ci.txt` is pinned, scanned by the `dependency scan` gate, and installed by
the `build` gate into a clean offline environment. Adding thirty heavyweight
dependencies — several carrying model weights measured in hundreds of megabytes — to the
file every CI job installs would slow every gate and risk the job timeouts, for tools no
code imports yet.

Engine dependencies therefore land **per engine, at its phase**, in a separate manifest,
with the twelve checks above satisfied before the tool is considered integrated. The
decision recorded here is permanent; the installation is staged.
