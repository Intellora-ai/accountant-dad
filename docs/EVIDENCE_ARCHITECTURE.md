# Evidence Architecture — how a citation is proven

**Status: implementation of a correction ordered 2026-08-05.** Replaces a check that
could not run on a fresh clone and could not tell a right section number from a wrong one.

---

## The defect this replaces

The original verifier asked one question:

```
does this quoted text appear somewhere in this file?
```

Two consequences, both demonstrated rather than argued.

**It passed a citation that was nonsense.** A claim citing `CGST Act s.999` — a section
that does not exist, in an Act the quote did not come from — carrying a quote taken from
ICAI AS-9 about dividends, verified green. Every word of the quote was real. A
500,000-character Act answers *"is this string present"* with yes for almost any short
phrase, so the question was close to no question at all.

**It could not run anywhere but one machine.** The source PDFs are 42 MB and gitignored.
The verifier required the `.pdf` to exist even though it read the `.txt` sidecar, so on a
fresh clone every VERIFIED claim failed with *"cites X, which is not downloaded."* The
mechanism that made the knowledge base trustworthy worked only where it had already been
run.

---

## The five proofs

Each is independent. **A failure in any one is a failure** — there is no warning tier and
no "verified except for the section" state. A citation exists to tell a reader where to
look, so a citation that is wrong about where it came from has failed at its only job.

| Layer | Question | Fails when |
|---|---|---|
| **1 · Document** | Is this the file we think, in the version we recorded? | absent from disk · bytes do not match the manifest sha256 · not declared at all |
| **2 · Section** | Does the cited section exist in that document? | `s.999` · `rule 900` · `AS 9 para 400` |
| **3 · Containment** | Does the quote lie **inside** that section's span? | real words, real document, wrong heading |
| **4 · Text** | Does the quote match, under declared normalisation? | one changed word · a "repaired" extraction artifact |
| **5 · Ownership** | Does the label belong to this document's grammar? | `AS 9 para 11` cited against the CGST Act |
| **6 · Metadata** | Does stored metadata agree with resolved metadata? | a hand-edited checksum · a source that moved under a citation |

Layer 3 is the one whose absence let `s.999` through. Layers 2 and 5 are what make a
section number **falsifiable** rather than decorative.

---

## What an author writes, and what the machine writes

```
AUTHORED     file · section · quote          (+ optional subsection · page ·
                                              paragraph · extraction_note)
RESOLVED     version · source_url · checksum · normalised · char_range ·
             retrieved · evidence_id
```

The author supplies only what a human can know: **which** document, **which** section,
**what** the quote is. Everything else is resolved from the manifest and computed from the
text, written back into the claim, and re-compared on every run.

**Why not hand-write the checksum?** A checksum typed into 700 places is 700 places to
forget when a source is re-fetched, and a stale checksum nobody compares is
indistinguishable from a correct one. Machine-written and machine-compared, or it is
decoration. A disagreement between stored and resolved is layer 6, and it fails.

---

## The manifest is the architecture

`Accounting_Brain/Evidence_Library/manifest.jsonl` used to record what happened to be on
disk. It now declares what the repository **requires**:

```json
{"file": "...", "title": "...", "body": "CBIC", "kind": "act",
 "version": "as amended up to 31.08.2021", "url": "https://...",
 "sha256": "...", "downloaded": "...", "bytes": 0, "extraction": "...", "defect": "..."}
```

`kind` selects the section parser. It is **declared, never inferred from the filename** —
renaming a file for clarity must never silently change how it is parsed.

`version` is what the **source** states about itself (`as enacted`, `as amended up to
31.08.2021`, `As on the 11th June, 2026`). Where a source declares no version, the field
says so explicitly rather than guessing one.

A document in the manifest and absent from disk is a **hard failure** naming the source
URL, the expected hash and the exact bootstrap command — never a quietly skipped check.

---

## Fresh clone

```
git clone
      ↓
python3 -m tools.evidence.bootstrap        fetch every declared source
      ↓                                     verify each against its sha256
python3 -m tools.evidence.verify           the five proofs, every citation
      ↓
identical results on every machine
```

`bootstrap --check` fetches nothing and reports precisely what is missing, so CI or an
air-gapped machine states the gap instead of failing with a stack trace.

**A download whose bytes do not match is deleted, not kept and flagged.** A
present-and-wrong document is more dangerous than an absent one: absence is loud and stops
the run, while a silently wrong version verifies every quote against text nobody chose.

### Why the text is committed and the PDF is not

| | committed | size | role |
|---|---|---|---|
| `.pdf.txt` sidecar | yes | 17 MB | what quotes are checked against — no PDF library needed, so results are identical everywhere |
| `.pdf` | no | 42 MB | anchors the sidecar to the government's bytes via the manifest checksum |

Both halves are needed. The sidecar alone would mean verifying an extraction against
itself, with nothing tying it to the official source.

---

## Parsers — one interface, many grammars

Indian legal sources do not agree on how to number themselves.

```
Act              16.  Eligibility and conditions for taking input tax credit.— (1)
Rules            46.  Tax invoice.-
ICAI standard    8.4  Dividends from investments in shares are not recognised
Notification     numbered paragraphs, plus tables keyed by Sl. No.
Rate schedule    almost pure tables, by HSN chapter
FAQ / guidance   numbered questions
```

Hardcoding one grammar would mean the verifier silently stops checking the moment a
document of another kind is cited. So every kind implements the same three questions:

```python
owns(label)       does this label BELONG to my grammar?          layer 5
sections(text)    what exists, and where does each span run?     layer 2
canonical(label)  the one true spelling of this label
```

**A kind with no parser is a hard error**, never a fallback to searching the whole file —
that fallback *is* the bug being removed. Adding a document of a new kind means writing
its parser first.

### The table-of-contents trap

Both the CGST Act and the Companies Act print a full contents listing before the body
using the same `N. Title` form. A parser taking the first match indexes every section to
its one-line contents entry, and then every containment check fails — or worse, a short
quote that happens to appear in a heading passes while the real provision is never
examined.

Resolved structurally, not by a page offset to maintain: contents entries are one-liners
packed adjacently, so the **body occurrence is the one with the most text before the next
heading**.

### Citation depth

A citation is written at the depth a lawyer writes it (`s.16(2)(a)`); a document prints
headings at the depth it prints them. Where the exact clause is parseable, containment is
checked against that clause. Where it is not, the nearest enclosing level is used **and
reported**, so the proof is never silently weaker than it looks.

---

## Normalisation — declared, not assumed

Three things are collapsed, and only three:

```
whitespace     a PDF breaks lines where the PAGE broke
typography     curly quotes, en/em dashes, non-breaking spaces are rendering choices
unicode form   NFKC, so composed and decomposed accents compare equal
```

Casing, wording, meaningful punctuation and digits are **never** touched:

```
thirty days          ≠  forty-five days      the invoice time limit
plant and machinery  ≠  plant or machinery   the defined term in s.17(5)(d)
September            ≠  November             a six-week ITC cut-off
shall                ≠  may                  a duty versus a discretion
```

Each of those pairs decides real money or a real duty, and each is a test.

**An extraction artifact is quoted around, never repaired.** Where the extractor fuses
words (`allsignificant`, `section133`), the quote is split into spans either side and an
`extraction_note` records why. "Tidying" the text into readable English makes the quote
unfindable in the source — correctly, since it would no longer be what the document says.

---

## Recorded gaps are not failures

```
VERIFIED                     proven through all six layers
UNKNOWN                      not yet researched
NO AUTHORITATIVE SOURCE      searched, nothing official found. NOT a licence to guess
REQUIRES HUMAN ACCOUNTANT    the law is silent or genuinely ambiguous
CONFLICT                     two authoritative sources disagree. Both recorded, neither dropped
```

A claim that says `UNKNOWN` is doing its job. Only a claim asserting `VERIFIED` and
failing to prove it is a defect. `CONFLICT` is never resolved by preference — picking one
silently is how a wrong entry acquires a paper trail.

---

## Commands

```bash
python3 -m tools.evidence.bootstrap           # fetch and checksum every source
python3 -m tools.evidence.bootstrap --check   # report gaps, fetch nothing
python3 -m tools.evidence.verify              # the five proofs
```

Tests: `tests/unit/test_evidence_verification.py` · `tests/unit/test_evidence_bootstrap.py`.
They run against a real parser and a real registry over a disposable evidence tree built
per test — what is synthetic is the *document*, never the machinery.

**Local runs are exploration. A result exists when CI produces it (Law 44).**
