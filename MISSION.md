# MISSION.md

> **Pointer, not a copy.** The mission and vision are stated in
> [`CLAUDE.md` §B](CLAUDE.md) — the constitution, which outranks this file.
> Duplicating them here would create a second place to update and one to forget.

## In one line

A user photographs a document or writes a sentence, and an **AI accountant** does the
accounting — as well as a human one.

## The two absolute non-goals

```
It must NEVER hallucinate.
It must NEVER post a wrong entry.
```

These are not preferences. They are why the architecture has **six separate engines
instead of one model**: every boundary in `docs/` exists to make one of them
*structurally impossible* rather than merely unlikely.

## Scope

| | |
|---|---|
| **Solves** | bookkeeping — later, audit, and eventually acting as a CA itself |
| **For** | businesses that want accounting without spending a lot on it, and those already overspending |
| **MVP** | integrated into **Tally**, Indian GST regime |
| **Stakes** | this posts entries into real businesses' books. A wrong entry is not a bug — it is a financial misstatement someone else answers for |

**Full text:** [`CLAUDE.md` §B](CLAUDE.md) · **Architecture:** [`ARCHITECTURE.md`](ARCHITECTURE.md)
