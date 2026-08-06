# benchmarks

Instruments. They **measure**; they never judge.

Nothing in this directory asserts a threshold, and nothing in it may be turned
into a merge gate without an approved number to gate on. `CLAUDE.md` Law 52:
*never fabricate a number, including a threshold.*
`.github/workflows/performance.yml`, on its own blocked gate: *"a gate missing
its number must never be given one."*

---

## `engine1_pipeline_benchmark.py`

Wall-clock latency of `accountant_dad.engines.input_engine.pipeline.run` — bytes
in, Document Evidence Object out — **per stage**, on real, manifest-declared
documents.

### ⚠ What these numbers are NOT a measurement of

**This repository contains no accounting document.** Not one invoice, receipt,
bill, voucher or challan, and **no image file of any format**. Its 40 PDFs are
statutes, rules, notifications, circulars and ICAI standards — every one of them
carrying a real text layer.

So every number this harness prints describes **text-layer PDF extraction on
legal documents**, and nothing else. A latency measured on an 880-page
Income-tax Act is **not** a claim about invoice processing, which is what
Engine 1 exists to do. Two of the paths that would dominate a photographed
receipt never execute here:

- `cleaner`'s deskew, denoise and contrast work — it operates on rendered
  pixels, and a text-layer PDF gives it nothing to correct
- `reader`'s OCR fallback — the text layer means it never fires

The harness prints this caveat with every report, and
`test_the_repository_declares_no_invoice_receipt_bill_or_scan` reads the real
manifest and goes red the day it stops being true. It is a checked fact, not a
disclaimer somebody remembered to write.

### Run it

```
PYTHONPATH=src python3 -m benchmarks.engine1_pipeline_benchmark
```

from the repository root. Options:

| Flag | Repeatable | Default | What it does |
|---|---|---|---|
| `--document` | yes | `CBIC-FAQ-Composition-Levy.pdf` | Which manifest entry to measure. Repeat it to measure several in one report |
| `--runs` | yes | `22` | Total runs, **including** the cold one. Give it once for all documents, or exactly once per `--document`, in the same order |
| `--manifest` | no | the repository's | Resolve the documents through a different manifest |

Several documents, each at its own run count:

```
PYTHONPATH=src python3 -m benchmarks.engine1_pipeline_benchmark \
  --document Notification-11-2025-Central-Tax.pdf      --runs 22 \
  --document CBIC-FAQ-Composition-Levy.pdf             --runs 22 \
  --document CGST-Act-2017-as-on-11062026-IndiaCode.pdf --runs 4
```

**Why per-document run counts exist.** This corpus runs from a 1-page
notification to an 880-page statute, and the pipeline's cost is dominated by a
stage that scales with pages. 22 runs of the Income-tax Act is hours; 22 runs
of a 1-page notification is seconds. A single shared run count would either
make the big document unmeasurable or make the small one's sample pointlessly
thin. Every document's own run count is printed on its own section and in the
index, so a small sample can never pass as a large one.

The source PDFs are gitignored — large, re-fetchable government bytes, hash
pinned by the manifest. If one is not on disk the benchmark refuses and prints
the command that fetches it:

```
python3 -m tools.evidence.bootstrap
```

It refuses just as loudly if the bytes on disk do not hash to what the manifest
declares, and every document is resolved and verified **before the first timer
starts** — a suite that runs for twenty minutes and then refuses its last
document has wasted the twenty minutes and tempts whoever ran it to report the
part that finished.

### What the output means

| Section | What it is |
|---|---|
| machine | Platform, processor, Python, CPU count. Printed **once**; a suite refuses two machines outright |
| settings | Every number handed to a sub-engine. A latency without these is not reproducible |
| index | One row per document: pages · warm runs · p50 · p95 · max · **which stage the time went to**. This is the table that answers "which document produced which number" |
| per document | Its own sha256, page count, kind, run counts, cold run, warm percentiles, and every run |
| cold run | Run 1 alone, stage by stage. The first `pipeline.run` in a process pays for model loading that no later run pays |
| warm runs | p50 · p95 · min · max over runs 2..N, per stage |
| every run | All N totals, cold one included — `MEASUREMENT_FRAMEWORK.md` §8, you may not run five times and report the best |

Two rows in the per-stage tables are not sub-engines:

- **`unattributed`** — time inside `pipeline.run` that is not inside any of the
  five timed calls: the temporary file `_parse_document` writes for Docling,
  the four small `*_output` repackagings, and the timers' own overhead. It is
  printed rather than absorbed into a stage, because a remainder that starts
  growing is a stage nobody is timing.
- **`total`** — the whole `pipeline.run` call.

`calls` is how many times that stage's function ran per document. It is there so
a per-document figure cannot quietly become a per-page one without anybody
noticing.

`kind` is the manifest's own word for the document — `act`, `rules`,
`notification`, `circular`, `guidance`, `icai_standard`. It is carried through
rather than described, so the report says what it measured without anybody
typing a claim about it.

### Why the percentiles are nearest-rank

`p50` and `p95` are values some run actually produced — index
`ceil(p/100 × n) − 1` of the sorted sample — never an interpolation between two
runs. `MEASUREMENT_FRAMEWORK.md` §2: in production the user gets one run, not
the mean of three.

**Nearest-rank p95 is simply the maximum for any warm sample below 20.**
`ceil(0.95n) == n` holds for every n up to 19 and fails first at n=20. Below
that the p95 column carries nothing the max column does not, so **the report
says so, on the line under the table**, naming the sample it has and the sample
it would need. It is derived from `nearest_rank` itself at render time, so the
warning and the number cannot drift apart.

> That boundary read **21** until 2026-08-06, from the stated ground that "p95
> equals the maximum for every sample of 20 or fewer". The sentence is false at
> exactly one value. It went unnoticed because the constant and the argument for
> it were checked against each other and never against `nearest_rank`. The test
> now sweeps every sample size from 1 to 40 against the real function.

`DEFAULT_RUNS` is 22 — 21 warm runs, one clear of the boundary. It is left at 22
rather than trimmed to 21 because a larger sample is strictly more evidence.

### What these numbers may and may not be used for

**May**: point at which stage the time goes to, and therefore at the current
constraint (`CLAUDE.md` §D.6).

**May not**:

- **Say anything about invoices.** See the warning at the top. The corpus is
  legal documents.
- **Pass or fail anything.** There is no approved performance floor for
  Engine 1. `MEASUREMENT_FRAMEWORK.md` §12 bounds the *whole six-engine
  pipeline* at ≤ 60 seconds per document, changeable only by amendment, and
  nobody has divided that between the six engines. Engine 1's share is a number
  the owner has not set, and inventing it here is forbidden.
- **Count as a result.** `MEASUREMENT_FRAMEWORK.md` §0a and Law 44: a result
  exists only if GitHub CI produced it. A local run of this harness is
  exploration, and every figure it prints carries the machine it came from for
  exactly that reason.
- **Be compared across machines**, or across changes to the settings block.
  Both are printed with every report so that a comparison which is not a
  comparison is visible rather than assumed. A suite refuses to be built from
  two machines or two settings blocks at all.

### How it is kept honest

`tests/unit/test_engine1_pipeline_benchmark.py` attacks the instrument rather
than the number:

- the stage list is re-derived from `pipeline.run`'s own source with `ast` and
  must equal the harness's — rename a stage in the pipeline and this goes red
- every probe must patch the exact module object `pipeline` resolves at call
  time, proven with `is`
- the timer must return the real function's exact result, proven by running
  real `cleaner.decode` bytes through it and comparing arrays
- a stage that was declared and never ran must raise, never report `0.000`
- a run whose stages exceed its total is refused at construction
- the report's field set is pinned, so it cannot grow a verdict by accident
- every printed setting must appear as a label, a gap, and its value — six of
  them silently ran into their own labels until 2026-08-06, and the column
  width is now derived from the content rather than assumed
- the p95 warning is checked against `nearest_rank` at 40 sample sizes, in both
  directions: it must fire when p95 really is the max, and must not otherwise
- the manifest declares no invoice, receipt, bill or image — the fact the
  corpus caveat rests on
