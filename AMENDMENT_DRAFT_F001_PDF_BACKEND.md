# AMENDMENT DRAFT — replace PyMuPDF with pypdfium2 as the PDF backend

> ## ⛔ DRAFT. NOT APPROVED. NOTHING HAS BEEN CHANGED.
>
> `docs/TECHNOLOGY_STACK.md` is **LOCKED** and line 28 names PyMuPDF as the PDF
> text-layer tool. This file **proposes** a change to it and carries the evidence a
> §M amendment requires. It does not make the change, and no line of
> `docs/TECHNOLOGY_STACK.md`, `requirements-engine1.txt`, `pyproject.toml` or
> `src/accountant_dad/pdf_backend.py` was touched in producing it.
>
> A locked component is not swapped on an engineer's judgement (`CLAUDE.md` §E.8,
> `KNOWN_FAILURES.md` F-001). **The decision below is the owner's.**

---

## Measurement state of this document — Law 56

| | |
|---|---|
| **Commit** | `fd479eb` — `test: three new suppressions would have reddened the ratchet…` |
| **Source** | a local macOS arm64 machine, Python 3.12.13, one process |
| **Status** | **`LOCAL ONLY — NOT AUTHORITATIVE`** (Law 44) |
| **CI evidence** | **NONE.** No number in this document was produced by GitHub Actions |

Every number below expires the instant `src/` changes after `fd479eb`. None of them is
a gate result and none may be quoted as one. They are inputs to a decision, and the
decision they support is *"do this next"*, never *"this is proven"*.

The full suite at `fd479eb` before any of this work: **3770 passed, 11 skipped, 0
failed**, 143.83 s — `LOCAL ONLY — NOT AUTHORITATIVE`.

---

## The eight-item §M record

### 1. What changed — old rule → new rule

| | |
|---|---|
| **Old rule** | `docs/TECHNOLOGY_STACK.md:28` — **PyMuPDF** · *"PDF text layer — no OCR needed when a PDF carries real text"*. Licence: *"Dual Licensed - GNU AFFERO GPL 3.0 or Artifex Commercial License"* |
| **New rule** | **pypdfium2** · the same capability, plus page rasterisation and PDF writing, which PyMuPDF was also silently providing. Licence: BSD-3-Clause and Apache-2.0, over a bundled PDFium binary that is BSD-3-Clause |
| **Scope** | `src/accountant_dad/pdf_backend.py` and its tests. **Nothing else.** No Engine 1 module names a PDF library — an AST sweep proves it — so the swap is a rewrite of one file |
| **Not changed** | The six-engine architecture · Engine 1's boundaries · every artifact schema · `pdf_backend`'s public surface, which keeps all eight of its names and signatures except where item 6 below states otherwise |

### 2. Which doc / section

- `docs/TECHNOLOGY_STACK.md` § *Engine 1 — Input Engine*, the PyMuPDF row
- `requirements-engine1.txt` — the `pymupdf==1.28.0` pin and its licence comment block
- `pyproject.toml` `[project].dependencies` — the `pymupdf==1.28.0` entry
- `KNOWN_FAILURES.md` F-001 — status moves from **CONTAINED, NOT CLOSED** to closed
- `tests/unit/test_pdf_backend.py` — `PDF_LIBRARY_NAMES` **gains** the new library's names; `"pymupdf"` and `"fitz"` **stay**, so removing the old one can never be undone silently

### 3. Why

`pypdfium2` is already a **pinned first-party dependency of this repository** —
`requirements-engine1.txt:104`, `pypdfium2==5.12.1`, installed and in use through
Docling. Adopting it as the PDF backend adds **no new distribution, no new transitive
dependency and no new supply-chain surface.** It removes one.

It also covers the whole surface alone. That was the open structural question and it is
answered by execution, not by reading documentation — see § *The structural verdict*.

### 4. What failure forced it

`KNOWN_FAILURES.md` **F-001**, severity HIGH, legal rather than technical.

`pymupdf==1.28.0` reports its licence, read from installed metadata on `fd479eb`, as:

```
$ python -c "import importlib.metadata as m; print(m.metadata('pymupdf')['License'])"
Dual Licensed - GNU AFFERO GPL 3.0 or Artifex Commercial License
```

and ships that same sentence as its entire `COPYING` file — 64 characters.

**AGPL-3.0 §13** obliges anyone who lets users interact with the software **over a
network** to offer those users the complete corresponding source. A hosted accounting
platform is exactly that shape. `CLAUDE.md` §B.1 states the product is one.

The owner ruled on **2026-08-06**: *"Do NOT purchase an Artifex licence. Keep PyMuPDF
temporarily. Immediately abstract it behind a PDF Engine interface so Engine 1 never
depends directly on PyMuPDF."* The abstraction was built and holds. **The exposure did
not change.** F-001 says so in its own words: *"until it is, this repository still ships
an AGPL dependency."*

Two lawful routes existed. The owner closed one. **This is the other one, costed.**

### 5. The trade-off — gain vs lose

#### Gained

| | Measured at `fd479eb`, `LOCAL ONLY — NOT AUTHORITATIVE` |
|---|---|
| The AGPL §13 exposure | **Removed.** BSD-3-Clause + Apache-2.0, no network clause anywhere in the 19 licence files the wheel ships |
| Supply chain | **Smaller by one distribution.** pypdfium2 5.12.1 is already pinned and installed |
| Disk | **7.52 MB → from 55.40 MB.** −86.4% |
| Cold import | **20.7 ms → from 46.4 ms.** −55.4%, best of 3, fresh interpreter |
| Text + character boxes | **10.94 ms/page → from 15.57 ms/page.** −29.7% over 219 pages |
| Rasterisation at 200 dpi | **41.9 ms/page → from 45.1 ms/page.** −7.1% |
| Self-consistency | pypdfium2's `plain_text` and `char_spans` return the same characters. PyMuPDF's do **not** — see § *What runs against the incumbent* |

#### Lost — every one of these is a real cost and none is hypothetical

| # | Cost | Size, measured |
|---|---|---|
| **L1** | **U+FFFE noncharacters where PyMuPDF reads a hyphen.** PDFium emits the Unicode noncharacter U+FFFE for glyphs in embedded subset fonts with no `ToUnicode` map | **862 across the corpus**, 658 of them replacing `-`. Rate **1.24–34.4 per 10,000 characters** on LaTeX and Ghostscript output. **0 on all four invoice-shaped fixtures.** Detectable: a noncharacter is never valid text |
| **L2** | **A 1-pixel taller raster at 150 and 300 dpi.** 1651 rows where PyMuPDF gives 1650, on US Letter | Deterministic — 10 identical calls give 1 distinct size and 1 distinct byte stream. Dimensions **agree exactly at 72, 96, 200 and 400 dpi** |
| **L3** | **Zero-page save does not refuse.** `PdfDocument.new()` then `save()` returns a valid **429-byte** PDF with no pages. PyMuPDF raises `ValueError: cannot save with zero pages` | `test_rebuilding_from_no_pages_refuses_rather_than_producing_an_empty_document` goes RED unless `pdf_of_page_images` adds an explicit refusal. **That test predicted this exact backend** — its docstring says so |
| **L4** | **PDFium has no span.** `reader.py:348-371` emits one `TextRegion` per PyMuPDF *span* — a run of one style. PDFium offers characters and *rects* — runs of one geometry | **78,464 rects vs 76,984 spans** corpus-wide (1.02x). Per fixture the ratio ranges **0.22x to 3.13x**. On both invoice fixtures it is **exactly 1.00x with identical text** |
| **L5** | **Rect text carries a trailing space** PyMuPDF's span text does not — `'Description '` vs `'Description'` | Visible in every region on every document. `reader.py:351` takes `span["text"]` verbatim |
| **L6** | **`PdfDocument(...)` is lazy.** A corrupt file can open and fail later, past the boundary `pipeline.BUSINESS_FAILURE` guards | The prototype forces the verdict by reading the page count inside `open_pdf`. With that one line, `corrupt.pdf` raises at `open` as required |
| **L7** | **Every Engine 1 number measured against PyMuPDF's boxes expires** (Law 56) | Coverage, mutation and every benchmark are re-measured on CI, once, at the end of the change set — ~3.4 h for mutation alone (`ENGINEERING_RULES.md`) |
| **L8** | **PNG resolution must be written explicitly.** PyMuPDF's PNGs carry `dpi=(199.9996, 199.9996)` at `dpi=200`; a Pillow-encoded pypdfium2 render carries `None` | Fixable in one argument. **Note F-028: the current code already loses this** through `cv2.imencode`, before any swap |

#### Not lost, checked because it was the obvious worry

| Checked | Result |
|---|---|
| Does it lose digits? | **No.** Whole-corpus conservation check: 25,928 digits vs PyMuPDF's 25,970. The 42-digit gap is **one page of one file**, and § *What runs against the incumbent* shows PyMuPDF is the one at fault there. **0 missing on 15 of 16 fixtures** |
| Does it corrupt a GST invoice? | **No.** An invoice with hyphens in invoice number, date, GSTIN, HSN, PO reference and a negative term reads **character-identical** in both, 12 hyphens each, 0 noncharacters each |
| Does it handle a scan with no text layer? | **Yes**, identically: 0 text characters, 0 boxes, and a raster of **exactly the same pixel dimensions**, on both `scanned_no_text_layer.pdf` and a 26 MB `image_only.pdf` |
| Is empty distinguishable from broken? | **Yes.** `blank.pdf` opens with 1 page and 0 characters; `corrupt.pdf` raises at `open`. `reader.py` is built on that distinction |
| Does it preserve page order on rebuild? | **Yes.** Three images of increasing width rebuild in order, and the result is readable by the other library |

### 6. The test that now guards it

**Nothing in `tests/unit/test_pdf_backend.py` is weakened, loosened or deleted.** The
F-001 import sweep is a zero-tolerance gate over the Engine 1 directory and stays one.

| Change | Direction |
|---|---|
| `PDF_LIBRARY_NAMES` gains `"pypdfium2"`, `"pypdfium2_raw"`, `"pdfium"` alongside the existing `"pymupdf"`, `"fitz"` | **STRICTER.** The old library's names are never removed — that is what makes the removal irreversible-by-test rather than by intention |
| `test_the_adapter_itself_is_where_the_library_is_named` asserts the adapter names exactly `{"pypdfium2"}` | Unchanged in shape; the anti-hollow-gate direction is preserved |
| `test_rebuilding_from_no_pages_refuses_rather_than_producing_an_empty_document` | **Unchanged, and it is the gate for L3.** It already anticipated this backend in prose |
| `test_a_page_renders_to_png_bytes_at_the_callers_dpi` | **Unchanged, and it is the gate for the DPI argument.** Both libraries pass it |

**New tests the swap requires**, each named for the cost it guards:

1. `test_a_glyph_the_font_cannot_map_never_reaches_a_caller_as_ordinary_text` — every
   character `plain_text` and `structured_text` return is a valid interchange
   character. Guards **L1**, and disqualifies the pdfminer family permanently.
2. `test_a_rebuilt_page_is_the_size_the_original_page_was` — guards **L8** and
   **F-028**. Red today, at every DPI other than 96.
3. `test_a_corrupt_pdf_is_refused_by_open_pdf_and_not_by_the_first_read` — guards
   **L6**, the lazy-open hazard.
4. `test_a_region_carries_no_whitespace_the_page_does_not` — guards **L5**.
5. `test_every_span_box_is_the_line_box_and_not_the_glyph_outline` — pins the
   `loose=True` choice. With `loose=False` the mean disagreement is **1.417 pt**;
   with `loose=True` it is **0.388 pt**. A silent flip of that flag would move every
   `SourceLocation` and no existing test would notice.

### 7. Who approved + date

```
Proposed by : Claude, 2026-08-06, on commit fd479eb
Evidence    : LOCAL ONLY — NOT AUTHORITATIVE. No CI run exists for any number here.

Approved by : ______________________     Date : ______________
Decision    : [ ] REPLACE with pypdfium2     [ ] STAY on PyMuPDF     [ ] MEASURE FURTHER
```

### 8. Then resume building

If **REPLACE**: rewrite `pdf_backend.py`, add the five tests above, run the full suite,
then pay the expensive gates **once** at the end of the change set (`ENGINEERING_RULES.md`
— mutation is ~3.4 h and is batched, not paid per commit). F-001 closes when CI is green
on the rewritten file, not before.

If **STAY**: F-001 stays open with its AGPL exposure unchanged, and this document records
what staying costs so the next session does not re-derive it.

---

## The candidate table — every licence read from the installed distribution

Read with `importlib.metadata` from the package pip actually installed, never from
memory and never from a web page.

```
$ python -c "import importlib.metadata as m; \
             print(m.metadata(NAME).get('License-Expression'), \
                   m.metadata(NAME).get('License'), \
                   [c for c in m.metadata(NAME).get_all('Classifier') or [] \
                    if c.startswith('License')])"
```

| Distribution | Version | Licence, as the package declares it | Field it came from | Verdict |
|---|---|---|---|---|
| **pymupdf** | 1.28.0 | `Dual Licensed - GNU AFFERO GPL 3.0 or Artifex Commercial License` | `License`, and the whole of `COPYING` | ❌ **incumbent. AGPL §13 applies to a hosted product** |
| **pypdfium2** | 5.12.1 | `BSD-3-Clause, Apache-2.0, dependency licenses` | `License` | ✅ permissive |
| **pdfplumber** | 0.11.10 | `License :: OSI Approved :: MIT License`, full MIT text shipped | `Classifier` + `licenses/LICENSE.txt` | ✅ permissive, ❌ **disqualified on behaviour** |
| **pdfminer.six** | 20260107 | `MIT` | `License-Expression` | ✅ permissive, ❌ **disqualified on behaviour** |
| **img2pdf** | 0.6.3 | `License :: OSI Approved :: GNU Lesser General Public License v3 (LGPLv3)`, full LGPLv3 text shipped | `Classifier` + `licenses/LICENSE` | ⚠️ **LGPL-3.0, NOT MIT** — see the correction below |
| **pillow** | 12.3.0 | `MIT-CMU` | `License-Expression` | ✅ permissive |
| **pikepdf** | 10.11.0 | `MPL-2.0` — pulled in by img2pdf | `License-Expression` | ⚠️ weak copyleft, file-level |
| **lxml** | 6.1.1 | `BSD-3-Clause` — pulled in by pikepdf | `License` | ✅ permissive |
| **cryptography** | 50.0.0 | `Apache-2.0 OR BSD-3-Clause` — pulled in by pdfminer.six | `License-Expression` | ✅ permissive |

> ### CORRECTION — `img2pdf` is **LGPL-3.0**, not MIT
>
> The task that produced this document stated *"`img2pdf` is MIT"*. It is not. The
> installed distribution carries the classifier `License :: OSI Approved :: GNU Lesser
> General Public License v3 (LGPLv3)` and ships the **full 7,652-character LGPLv3
> text** as `img2pdf-0.6.3.dist-info/licenses/LICENSE`.
>
> LGPL has **no network clause** — there is no §13 — so it is not the same hazard as
> AGPL. It is still copyleft, it still carries relinking obligations, and it drags in
> `pikepdf` (MPL-2.0). **It is also unnecessary:** pypdfium2 writes PDFs on its own,
> proven below.

### pypdfium2 bundles a compiled binary, so its own SPDX expression is not the whole answer

The wheel ships `pypdfium2_raw/libpdfium.dylib`, 7.2 MB. Every licence file in the
distribution was read and swept for copyleft — 19 files:

```
LICENSES/Apache-2.0.txt          LICENSES/BSD-3-Clause.txt      LICENSES/CC-BY-4.0.txt
BUILD_LICENSES/pdfium.txt        (Copyright 2014 The PDFium Authors — BSD-3-Clause)
BUILD_LICENSES/abseil.txt        BUILD_LICENSES/agg23.txt       BUILD_LICENSES/fast_float.txt
BUILD_LICENSES/freetype.txt      BUILD_LICENSES/icu.txt         BUILD_LICENSES/lcms.txt
BUILD_LICENSES/libjpeg_turbo.ijg BUILD_LICENSES/libjpeg_turbo.md
BUILD_LICENSES/libopenjpeg.txt   BUILD_LICENSES/libpng.txt      BUILD_LICENSES/libtiff.txt
BUILD_LICENSES/llvm-libc.txt     BUILD_LICENSES/simdutf.txt     BUILD_LICENSES/zlib.txt
BUILD_LICENSES/pdfium-binaries.txt
```

**No AGPL. No LGPL.** One GPL reference exists and is reported rather than hidden:
`icu.txt` lines 464–531 cover **ICU4C's build scripts** — `aclocal.m4`, `config.guess`,
`install-sh` — under GPL-2.0/GPL-3.0 **with the Autoconf exception**, which ICU's own
notice states is satisfied. Those files are build tooling and are not linked into the
shipped library. The sweep that found it was self-tested in both directions: it fires on
an AGPL header and stays silent on MIT.

---

## The structural verdict — can any single library cover the whole surface?

`src/accountant_dad/pdf_backend.py` owns exactly eight things. Each was **called** on
every candidate. A capability that is claimed and never called is a capability nobody has.

| Operation | pymupdf 1.28.0 | pypdfium2 5.12.1 | pdfplumber 0.11.10 | pdfminer.six 20260107 | img2pdf 0.6.3 |
|---|---|---|---|---|---|
| `open_pdf(bytes)` | ✅ | ✅ | ✅ | ✅ | ❌ |
| `page_count` | ✅ 18 | ✅ 18 | ✅ 18 | ✅ 18 | ❌ |
| `plain_text` | ✅ | ✅ | ✅ | ✅ | ❌ |
| `structured_text` **with boxes** | ✅ | ✅ | ✅ | ✅ | ❌ |
| `render_page_png(dpi=…)` | ✅ | ✅ | **⚠️ only via pypdfium2** | ❌ | ❌ |
| `pdf_of_page_images` | ✅ | ✅ | ❌ | ❌ | ✅ |
| `close_pdf` | ✅ | ✅ | ✅ | ✅ | ❌ |
| a broken-file verdict at `open` | ✅ | ✅ | ⚠️ raises `PdfminerException` | ✅ | ❌ |
| **covers the surface alone** | **YES** | **YES** | no — 5 of 8 | no — 5 of 8 | no — 1 of 8 |

### The claim in the task, tested rather than repeated

The task said pdfplumber/pdfminer *"cannot rasterise a page or WRITE a PDF"* and asked
for proof either way. **Half of it is false and the correction matters.**

1. **pdfplumber CAN rasterise.** `page.to_image(resolution=150)` returned a
   `1275 x 1651 px` PIL image. The flat claim is withdrawn.
2. **Its only rasteriser is pypdfium2.** With `pypdfium2` made unimportable, the same
   call raised `ModuleNotFoundError: No module named 'pypdfium2'`. `pdfplumber/display.py:7`
   is literally `import pypdfium2`. **Choosing pdfplumber for rasterisation is choosing
   pypdfium2 with a layer on top, not choosing an independent renderer.**
3. **pdfminer.six has no PDF output and no rasteriser.** Its exported converters are
   `HOCRConverter`, `HTMLConverter`, `TextConverter`, `XMLConverter`. There is no
   `save`, `write_pdf` or `to_pdf` anywhere in the package.

**Therefore:** the pdfplumber/pdfminer family could only ever cover
`plain_text`/`structured_text`, and a full replacement built on it would need
pypdfium2 underneath anyway. **pypdfium2 alone is the only single-library answer.**
`img2pdf` is not needed, which also disposes of its LGPL.

---

## The measured comparison

**Corpus.** The repository ships **no PDF fixture** — every one in `tests/` is built at
runtime by `a_text_layer_pdf()` with PyMuPDF, so a comparison run only on those would be
PyMuPDF grading its own output. The corpus is therefore **16 documents, 219 pages**:

- **2 authored** — the exact shapes `tests/unit/test_pdf_backend.py` builds
- **14 foreign** — produced by six unrelated toolchains: pdfTeX 1.40.17/.21/.25,
  GNU Ghostscript 5.50/7.05, AFPL Ghostscript 8.54 + dvips, GPL Ghostscript 9.22,
  PDF Architect, and three hand-written PDFs with no producer string

Producers were read with **pypdfium2**, not PyMuPDF — asking PyMuPDF whether a file is
its own output is the circularity the corpus exists to remove.

### (a) Text — does it read the same characters?

Baseline `pymupdf 1.28.0`. Similarity is `difflib.SequenceMatcher` over whitespace-collapsed text.

| Library | pages | byte-exact | same chars | mean similarity | worst page | net char delta | **ms/page** |
|---|---|---|---|---|---|---|---|
| **pypdfium2** | 219 | 1 | 20 | **0.9704** | 0.4875 | **+311** | **13.97** |
| pdfplumber | 219 | 1 | 23 | 0.8271 | 0.0617 | +11,323 | 65.08 |
| pdfminer.six | 219 | 26 | 60 | 0.8834 | 0.0228 | +9,971 | 47.60 |
| *pymupdf (baseline)* | 219 | — | — | — | — | — | 17.71 |

Character-level: **pypdfium2 differs on 6,103 of 510,041 characters — 1.197%.** The
largest class is **NFKC-equal Unicode normalisation** (1,324 runs: `ﬁ` → `fi`), which
changes no information.

### (b) The disqualifying finding — pdfminer.six and pdfplumber **fabricate digits**

`CLAUDE.md` §B.8 states an absolute non-goal: ***"It must NEVER hallucinate."*** That
obligation does not begin at Engine 2.

When a font carries no `ToUnicode` map, pdfminer.six does not fail and does not emit a
replacement character. **It emits the literal ASCII string `(cid:28)`.**

| Library | digits emitted | `(cid:N)` tokens | digits **inside** them | **% of digits fabricated** | pages affected |
|---|---|---|---|---|---|
| pymupdf | 25,970 | 0 | 0 | **0.00%** | 0 / 219 |
| **pypdfium2** | 25,928 | 0 | 0 | **0.00%** | 0 / 219 |
| pdfplumber | 28,659 | 1,388 | 2,660 | **9.28%** | **79 / 219** |
| pdfminer.six | 28,659 | 1,388 | 2,660 | **9.28%** | **79 / 219** |

The same page, four libraries:

```
pymupdf        '…Thisnumber,AiD*,\x10inourexperiments,'
pypdfium2      '…Thisnumber,AiD*,\x10inourexperiments,'
pdfplumber     '…Thisnumber,Ai(cid:28)D*,(cid:16)inourexpe…'
pdfminer.six   '…number,Ai(cid:28)D*,(cid:16)toreducet…'
```

Those digits correspond to **no glyph on the page** — they are font-internal glyph
identifiers rendered as text. They are ordinary ASCII, indistinguishable from a printed
`28`, and **no filter can reject them.** This is disqualifying for a system that posts
into books, independently of everything else in this document.

**Detectability is the whole difference between the two failure modes:**

| Library | chars | U+FFFE noncharacters | C0/C1 controls | unassigned | **machine-detectable corruption** | **undetectable fabrication** |
|---|---|---|---|---|---|---|
| pymupdf | 612,329 | 0 | 690 | 0 | 0.113% | **0** |
| pypdfium2 | 625,925 | 862 | 743 | 0 | 0.256% | **0** |
| pdfplumber | 580,811 | 0 | 0 | 0 | 0.000% | **2,660 digits** |
| pdfminer.six | 624,811 | 0 | 0 | 0 | 0.000% | **2,660 digits** |

A Unicode noncharacter can never be valid text, so three lines of code reject it.
`(cid:28)` passes every such filter.

### (c) Bounding boxes — does it put them in the same place?

**505,774 characters aligned** by `difflib` equal-runs, so a single ligature does not
throw away a whole page of box evidence. Units: **PDF points, 1/72 inch.** Convention:
`(left, top, right, bottom)`, origin **top-left** — PyMuPDF's, because it is the one every
`SourceLocation` in this repository is already expressed in.

**Native conventions, which is the finding the task asked for:**

| Library | what its API returns natively |
|---|---|
| **pymupdf** | top-left origin, y **down**, PDF points — no conversion |
| **pypdfium2** | bottom-left origin, y **UP**, PDF points — `height − y` on both edges |
| **pdfminer.six** | bottom-left origin, y **UP**, PDF points (`LTChar.bbox`) — same flip |
| **pdfplumber** | **both**: `x0/x1` + `top/bottom` are top-left; `y0/y1` are bottom-left |

**After conversion:**

| Candidate | chars | mean \|d\| | median \|d\| | p99 \|d\| | max \|d\| | mean dx | mean d(top) | mean d(bottom) |
|---|---|---|---|---|---|---|---|---|
| pypdfium2 `loose=False` | 505,774 | 1.417 pt | 0.574 pt | 6.133 pt | 310.3 pt | +0.009 | +2.988 | −2.034 |
| **pypdfium2 `loose=True`** | 505,774 | **0.388 pt** | **0.036 pt** | **4.771 pt** | 309.9 pt | −0.017 | +1.134 | −0.274 |
| pdfplumber | 506,929 | 0.250 pt | 0.008 pt | 2.700 pt | 26.5 pt | +0.002 | +0.286 | −0.318 |
| pdfminer.six | 472,040 | 0.597 pt | 0.010 pt | 2.700 pt | 520.2 pt | −0.044 | +0.343 | −0.235 |

PDFium offers two box shapes per character and **they are not interchangeable**:
`loose=False` is the tight glyph outline, `loose=True` spans the line's ascent and
descent. PyMuPDF's `rawdict` bbox is the second kind. Choosing wrong costs **3.7x** the
disagreement — 1.417 pt against 0.388 pt — which is why test 5 in item 6 pins it.

**If the y flip is forgotten**, which is the silent corruption the task named:

| Candidate | mean \|d\| | median \|d\| | max \|d\| | as a multiple of a glyph |
|---|---|---|---|---|
| pypdfium2 | **155.9 pt** | 1.66 pt | **792.4 pt** | **15.1x** |
| pdfminer.six | 155.9 pt | 2.22 pt | 793.5 pt | 15.0x |

Mean glyph box height in the corpus: **10.34 pt**. A forgotten flip is a mean error of
**fifteen glyph heights** and a maximum of **a whole page**, in numbers that stay
positive, stay on the right page and stay in the right units. **Nothing downstream would
reject them.**

### (d) Rasterisation — is the caller's DPI honoured?

**`render_page_png` has no default DPI anywhere in this repository, deliberately**
(`pdf_backend.py:229`). The argument is load-bearing, so the first question is whether it
does anything at all.

| dpi | exact w x h, US Letter | pymupdf | pypdfium2 | agree |
|---|---|---|---|---|
| 72 | 612.00 x 792.00 | 612x792 | 612x792 | ✅ |
| 96 | 816.00 x 1056.00 | 816x1056 | 816x1056 | ✅ |
| **150** | 1275.00 x 1650.00 | 1275x**1650** | 1275x**1651** | ❌ |
| 200 | 1700.00 x 2200.00 | 1700x2200 | 1700x2200 | ✅ |
| **300** | 2550.00 x 3300.00 | 2550x**3300** | 2550x**3301** | ❌ |
| 400 | 3400.00 x 4400.00 | 3400x4400 | 3400x4400 | ✅ |

Both honour the argument — doubling the DPI doubles both dimensions (ratios 1.9988–2.0000).
Both are **deterministic**: ten identical calls produce one distinct size and one distinct
byte stream each. The 1-pixel difference is L2, and it is a rounding disagreement, not
randomness.

**Pixel equivalence at 200 dpi, where dimensions agree exactly so no resize is involved:**

| | |
|---|---|
| Dimension mismatches | **0 of 16 fixtures** |
| Mean absolute pixel difference | **2.126 of 255 — 0.83%** |
| Pixels more than 32 apart | **2.276%** |
| Removed by a 4x box downsample | 46.6% |
| Mean ink difference, pdfium − pymupdf | **+0.287 of 255**, positive on **15 of 16** fixtures |
| Pixels where pymupdf is darker / pdfium is darker | **1.53% / 1.97%** |

> **A withdrawn measurement.** An earlier version of this comparison ran at 150 dpi,
> where pypdfium2 returns one extra row, and resized one image before subtracting. That
> resample shifts every glyph by a fraction of a pixel and manufactures a difference at
> every edge in the document. It reported **1.24%** and it was measuring my own
> resampler. **Withdrawn and replaced by the 200 dpi figure above.**

The difference is **glyph weight, not content**: pdfium renders consistently slightly
darker, and the differing pixels split roughly evenly in both directions — the signature
of edge rendering. Missing content would be one-directional and localised.

**On the scanned path**, which is Engine 1's other real input:

| fixture | pymupdf | pypdfium2 |
|---|---|---|
| `scanned_no_text_layer.pdf` (0.62 MB) | 1 page, 0 text, render 1653x2339 | 1 page, 0 text, render **1653x2339** |
| `image_only.pdf` (26.11 MB) | 1 page, 0 text, render 1653x2339 | 1 page, 0 text, render **1653x2339** |

### (e) Writing a PDF from page images, and the round trip

Three PNGs of increasing width — the repository's own order fingerprint.

| writer | output | pages | rebuilt page widths | order preserved | readable by the other library |
|---|---|---|---|---|---|
| pymupdf | 9,574 B | 3/3 | 120, 240, 360 pt | ✅ | ✅ |
| **pypdfium2** | **2,550 B** | 3/3 | 160, 320, 480 pt † | ✅ | ✅ |
| img2pdf | 3,419 B | 3/3 | 120, 240, 360 pt | ✅ | ✅ |

† the prototype used pixels as points. **With the render DPI passed explicitly,
pypdfium2 reproduces PyMuPDF's page geometry exactly:**

| source | dpi | pymupdf rebuild | pypdfium2 @96 | **pypdfium2 @ render dpi** |
|---|---|---|---|---|
| A4 invoice, 595x842 pt | 200 | 595.08 x 842.04 | 1239.75 x 1754.25 | **595.08 x 842.04** ✅ |
| A4 invoice, 595x842 pt | 300 | 595.20 x 842.16 | 1860.00 x 2631.75 | **595.20 x 842.16** ✅ |
| Letter, 612x792 pt, 3 pages | 200 | 612 x 792 | 1275 x 1650 | **612 x 792** ✅ |
| Letter, 612x792 pt, 3 pages | 300 | 612 x 792 | 1912.5 x 2475 | **612 x 792** ✅ |

**Zero pages — the case the repository already pins:**

| library | native behaviour |
|---|---|
| pymupdf | `ValueError: cannot save with zero pages` |
| **pypdfium2** | **returns a valid 429-byte PDF with no pages** ← **L3** |
| img2pdf | `ValueError: Unable to process empty list` (different message) |

### (f) The broken-file verdict — what `BrokenPdfError` derives from

Input: `corrupt.pdf`, 39 bytes, `b'%PDF-1.4\nthis is not a pdf body at all\n'`.

| library | at `open` |
|---|---|
| pymupdf | `pymupdf.FileDataError: Failed to open stream` |
| **pypdfium2** | **`pypdfium2.PdfiumError: Failed to load document (PDFium: Data format error).`** |
| pdfminer.six | `PDFSyntaxError: No /Root object! - Is this really a PDF?` |
| pdfplumber | `pdfplumber.utils.exceptions.PdfminerException` — wraps it in its own type |

**`BrokenPdfError` would derive from `pypdfium2.PdfiumError`**, converted at the same
boundary, carrying the message verbatim exactly as today. `PdfiumError` is broader than
`FileDataError` — L6 — so `open_pdf` must force the verdict at open.

**Empty is not broken** — `blank.pdf` opens on all four with 1 page, 0 characters, 0 boxes.

### (g) Cost

| | pymupdf 1.28.0 | **pypdfium2 5.12.1** | pdfplumber | pdfminer.six | img2pdf |
|---|---|---|---|---|---|
| on disk | 55.40 MB | **7.52 MB** | 21.25 MB | — | 33.51 MB |
| largest file | `libmupdf.dylib` 33.3 MB | `libpdfium.dylib` 7.2 MB | `_rust.abi3.so` 11.8 MB | — | `lxml/etree…so` 9.5 MB |
| cold import | 46.4 ms | **20.7 ms** | 51.8 ms | 45.4 ms | 45.5 ms |
| text + boxes | 15.57 ms/page | **10.94 ms/page** | 65.08 ms/page | 47.60 ms/page | — |
| render 200 dpi | 45.1 ms/page | **41.9 ms/page** | via pdfium | ❌ | ❌ |

---

## What runs against the incumbent

Confirmation bias would stop at *"the candidate is 42 digits short"*. Chasing that number
found the opposite.

**On `fieldaware.pdf` page 4, PyMuPDF's `plain_text` returns 114 digits its own
`char_spans` cannot locate.**

| | pymupdf | pypdfium2 |
|---|---|---|
| `plain_text`, collapsed | 4,231 chars, 182 digits | 3,330 chars, 58 digits |
| `char_spans`, visible | **3,409 chars, 68 digits** | **3,330 chars, 58 digits** |
| self-consistent | **NO — 822 characters have no box** | **YES** |

The 901-character block PyMuPDF adds is
`'bP1FsdL626dBNsBd2UmSrozoILivYC7RDyaSZNja…'` — and it appears in **zero** of the 618
spans `get_text("rawdict")` reports for that page. pypdfium2's text matches PyMuPDF's
**located** text at ratio **0.9847**, against **0.8777** for its unlocated text.

**The entire 42-digit corpus-wide gap is one page, and on that page the incumbent is
emitting characters it cannot place.** `reader.py` builds a `SourceLocation` for every
region; 822 characters with no box could not have one.

Separately, and independent of any backend choice: **`cleaner` currently produces rebuilt
scans `render_dpi / 96` times the original page size** — 3.126x at 300 dpi. Recorded as
**`KNOWN_FAILURES.md` F-028**, not fixed (`CLAUDE.md` §E.7).

---

## Recommendation, and the failure mode that would prove it wrong

### REPLACE PyMuPDF with pypdfium2.

Because, in order of weight:

1. **The licence exposure is real, live, and the owner closed the other route.** F-001
   is HIGH severity and open. Containment changed the blast radius, not the exposure.
2. **The replacement is already a pinned dependency of this repository** —
   `requirements-engine1.txt:104`. Adopting it removes a distribution instead of adding one.
3. **It covers all eight operations alone**, proven by calling all eight.
4. **It is measurably not worse on the two things that matter** — 0.388 pt mean box
   disagreement over half a million characters, and 0.83% mean pixel difference that is
   glyph weight rather than content.
5. **It is cheaper on every axis measured** — 86% less disk, 55% faster import, 30%
   faster text.
6. **The only alternative family fabricates digits** on 36% of pages.
7. **It is more self-consistent than the incumbent**, and that finding was hunted for
   rather than stumbled on.

### The failure mode — what would make this recommendation wrong

**L1, the U+FFFE substitution, on a document population this corpus does not contain.**

The corpus is 12 academic papers and 4 synthetic invoices. **It contains zero real GST
invoices, zero scanned Indian tax documents and zero Tally exports** — the MVP's actual
input. The substitution fires on embedded subset fonts with no `ToUnicode` map, at
**1.24–34.4 per 10,000 characters** on LaTeX and Ghostscript output, and at **zero** on
every invoice-shaped fixture. If Indian GST software emits subset fonts without
`ToUnicode` — plausible, and **unmeasured** — then pypdfium2 would corrupt hyphens in
invoice numbers, GSTINs and HSN codes.

**Three properties keep that from being fatal, and all three are load-bearing:**

- It is **detectable**. U+FFFE can never be valid text; test 1 of item 6 rejects it.
- It is **detectable at the reader**, before any accounting reasoning sees it.
- The alternative failure — pdfminer's `(cid:28)` — is **not** detectable at all.

**The cheap experiment that would settle it**, and it should be run before the rewrite
rather than after: take **ten real GST invoice PDFs**, run both libraries, and count
noncharacters. If the count is zero, ship. If it is not, the ligature and hyphen mapping
needs a fallback before the swap — and P1's golden set is where those ten documents come
from anyway.

**What I am not claiming.** No number here is CI-produced (Law 44), so none is a result.
No accuracy claim about Engine 1 is provable at all until P1 exists (`CLAUDE.md` §P).
This document argues *"do this next"*. It does not argue *"this is proven"*.

---

## Reproducing the numbers

The prototypes are in the session scratchpad at `…/scratchpad/f001/`, in a throwaway
virtualenv holding `pymupdf==1.28.0`, `pypdfium2==5.12.1`, `pillow==12.3.0`, `pdfplumber`,
`pdfminer.six` and `img2pdf`.

**Nothing was installed into the repository's environment.** `requirements-ci.txt`,
`requirements-engine1.txt`, `requirements-engine1-ocr.txt` and `pyproject.toml` are
unchanged.

**The harness is deliberately not committed.** `ruff check .` and `ruff format --check .`
run over the whole tree, and prototype code written to exercise four libraries' untyped
APIs would need new suppressions — which the ratchet only lets fall. The numbers are
recorded here in full instead; if the amendment is approved, the checks worth keeping
become the five real tests in item 6.

| Script | What it produces |
|---|---|
| `licences.py` · `pdfium_licences.py` | the candidate table and the 19-file copyleft sweep |
| `corpus.py` | the 16 fixtures and their producers |
| `capability.py` · `falsify_readonly.py` | the eight-operation matrix and the read-only proof |
| `measure_text.py` · `measure_diffs.py` | text fidelity and the classified disagreements |
| `measure_digits.py` · `measure_cid_fabrication.py` | the digit conservation check and the fabrication finding |
| `measure_boxes.py` | box residuals, converted and unflipped |
| `measure_render.py` · `measure_render_clean.py` · `measure_render_detail.py` | DPI, determinism, pixel equivalence |
| `measure_write_and_failure.py` | round trip, zero pages, corrupt input |
| `measure_regions.py` · `measure_cost.py` | region granularity, speed, footprint |
| `redteam_hyphen.py` · `investigate_fieldaware.py` · `who_is_wrong.py` | the attacks on this recommendation |
| `probe_geometry.py` | F-028, through the real `accountant_dad.pdf_backend` |
