# Accounting Brain

Knowledge the six engines consume. **Advisory, never binding** — the Knowledge Brain
informs a decision, it never makes one (`CLAUDE.md` §O, standing architectural rules).

> **The single rule this whole directory rests on.** Every claim carries a source that
> was READ, not remembered. `CLAUDE.md` Law 36: *never allow AI-generated knowledge into
> canonical storage without verification.* A rule written from model memory is
> indistinguishable from a correct one until it posts a wrong entry into someone's books.
>
> There is no penalty for `UNKNOWN`. There is no recovery from a fabricated citation.

## How a claim becomes legitimate

```
1. the source document is DOWNLOADED into Evidence_Library/sources/
2. its SHA-256 is recorded in Evidence_Library/manifest.jsonl
3. text is EXTRACTED from that local copy
4. the claim quotes that text VERBATIM
5. verify_evidence.py re-opens the local file and confirms the quote is in it
```

Step 5 is what makes the rest true. `tests/unit/test_conformance_registry.py` already does
exactly this for the 23 locked documents — it opens each cited file, reads the cited line,
and fails if the quote drifted. The same principle applies here, against downloaded law.

**A quote that cannot be found in a downloaded source is not a citation. It is a guess
wearing one, and it must be recorded as `NO AUTHORITATIVE SOURCE FOUND` instead.**

## Authoritative sources, in priority order

| Priority | Body | What it settles |
|---|---|---|
| 1 | Gazette of India | the enacted text |
| 1 | CBIC — `cbic-gst.gov.in`, `taxinformation.cbic.gov.in` | CGST/IGST Acts, Rules, Notifications, Circulars |
| 1 | Income Tax Dept — `incometaxindia.gov.in` | Income Tax Act, TDS |
| 1 | MCA — `mca.gov.in` | Companies Act, schedules, depreciation |
| 2 | ICAI — `icai.org` | Accounting Standards, Guidance Notes |
| 2 | RBI — `rbi.org.in` | banking, forex where relevant |

**Primary beats secondary, always.** A summary of the law is not the law. A blog is never
a source. Where a notification amends an Act, both are cited and the amendment wins.

## Status vocabulary — every concept carries exactly one

```
VERIFIED                     quote confirmed present in a downloaded source
UNKNOWN                      not yet researched
NO AUTHORITATIVE SOURCE      searched, nothing official found. NOT a licence to guess.
REQUIRES HUMAN ACCOUNTANT    the law is silent or genuinely ambiguous; judgement needed
CONFLICT                     two authoritative sources disagree. Both recorded, neither dropped.
```

`CONFLICT` is never resolved by preference. It is recorded with both citations and left
for a human, because picking one silently is how a wrong entry gets a paper trail.

## Directories

| Directory | Holds |
|---|---|
| `Knowledge_Tree/` | the hierarchy, organised by DECISION not by book |
| `Atomic_Concepts/` | one file per concept, the 19 fields |
| `Decision_Trees/` | what an accountant checks first, second, and why |
| `Rule_Library/` | atomic IF/THEN rules, independently addressable |
| `Exception_Library/` | exceptions, special cases, industry rules |
| `Validation_Library/` | how to verify a decision, and how it fails |
| `Evidence_Library/` | downloaded sources + hash manifest |
| `Knowledge_Graph/` | nodes and edges between concepts |
| `Cross_References/` | dependency links |
| `Reasoning_Chains/` | worked chains from document to entry |
| `Confidence_Metadata/` | what makes a determination weak or strong |
| `Missing_Knowledge/` | the registry of every gap, by status above |

## What this directory must never contain

- A rule with no citation
- A citation to a document not in `Evidence_Library/sources/`
- A quote that `verify_evidence.py` cannot find in that document
- A tax rate, threshold, due date or section number written from memory
- A resolved `CONFLICT`
- Anything that reads as advice rather than as recorded law

## Build freeze

`CLAUDE.md` §P freezes accounting and tax logic in `src/`. This directory is
**knowledge, not engine code** — no engine reads it yet, and nothing here executes.
It is built now so that P4 has something verified to consume.
