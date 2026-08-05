# SESSION_LOG.md

> **Per-session index.** The engineering detail — what changed, which tests ran, which
> numbers moved — lives in [`PROGRESS.md`](PROGRESS.md). This file is the shorter
> question: what happened in each session, and where did it stop.

---

## 2026-08-05 · Engine 1 built end to end

**Started:** Engine 1 was one sub-engine (`cleaner`) and a mutation gate that had never
once finished.

**Ended:** Engine 1 complete — nine modules, ~4,000 lines of source and ~4,500 of tests.
Seven of eight CI gates green. Mutation still red.

**Landed:** `reader` · `parser` · `assembly` · `confidence` · `classification` · `config`
· `measurement` · `pipeline` · the confidence specification (666 lines) · seven atomic
concepts · the five memory documents · the `gate.yml` dependency fix · the mutation cap
at the owner's 500.

**Defects found that unit tests could not see:** F-011 (`cleaner` cannot decode a PDF),
F-012 (the pipeline is not a pipe), F-013 (no per-field confidence is reachable), F-015
(the Table Transformer is rebuilt once per table).

**Two false greens withdrawn.** A "2068 passed" cited as evidence had run against
`numpy 2.3.5` / `cv2 4.10.0` while the manifest pinned `2.5.1` / `5.0.0.93`.

**Survived:** a session limit killed roughly 30 agents mid-run. Nothing was lost — every
worktree was recovered and finished rather than restarted. That is why the memory
documents now exist.

**Stopped at:** the `mutation` baseline failing inside `mutants/`. See
[`STATE.md`](STATE.md).
