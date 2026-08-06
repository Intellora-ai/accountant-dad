# DEFINITIONS — the register

**Law 54. Never build on a word that has no definition, and never invent the
definition yourself — ask.**

```
not measurable  ->  not provable  ->  not true  ->  FALSE
```

**An undefined term in a specification is a false statement waiting to be discovered.**

---

## THE RULE

A term enters this register when it becomes **load-bearing** — when a decision, a
gate, a threshold or an artifact depends on what it means. Each entry carries:

```
Term          the word
Definition    ONE engineering definition, in this repository, for all time
Measurement   how it is obtained — the instrument, the unit, the procedure
Owner         the PERSON who approved the definition
Status        DEFINED (with the doc that holds it) | UNDEFINED — blocks work
```

**A term with `Status: UNDEFINED` blocks any work that depends on it.** That is not
obstruction; it is the only honest state, because building on it produces a number
nobody can defend.

---

## THE PRODUCT TERMS — `docs/ACCOUNTING_DEFINITIONS.md` is canonical

These are the six the architecture depends on. **This file is the index; that document
is the authority.** Duplicating the definitions here would fork them, which is
anti-pattern F1.

| Term | Where it is load-bearing | Status |
|---|---|---|
| **Correct** | what Engine 5 validates | `docs/ACCOUNTING_DEFINITIONS.md` |
| **Safe** | validation's core question — *"is this safe to post?"* | `docs/ACCOUNTING_DEFINITIONS.md` |
| **Understanding** | Engine 2's entire output | `docs/ACCOUNTING_DEFINITIONS.md` |
| **Risk** | two separate artifacts | `docs/ACCOUNTING_DEFINITIONS.md` |
| **Doubt** | Engine 3's output | `docs/ACCOUNTING_DEFINITIONS.md` |
| **Uncertainty** | travels through every engine | `docs/ACCOUNTING_DEFINITIONS.md` |
| **Confidence** | six separate layers of it | `docs/CONFIDENCE_SPECIFICATION.md` · `docs/ENGINE_1_CONFIDENCE_PARAMETERS.md` |

**Confidence carries a standing constraint:** every threshold, weight and cutoff is a
**named configuration variable** with its purpose, valid range, units, and what changes
when it moves. **No hardcoded defaults. No silently assumed values. Missing required
confidence configuration fails fast at startup, never falls back.** A system may not
assert `confidence >= 0.90` until it can show why 0.90 is the correct operating point
for the data collected.

**And a binding one:** confidence gates NOTHING until calibration is proven (owner
decision A7, `docs/MEASUREMENT_FRAMEWORK.md` §10).

---

## THE MEASUREMENT TERMS

| Term | Definition | Measurement |
|---|---|---|
| **MEASURED** | an observation was made | the command that produced it is quoted |
| **DERIVED** | follows from a measurement | the arithmetic is stated |
| **INFERRED** | plausible, not observed | labelled as such, never as fact |
| **UNKNOWN** | not established | always an acceptable answer |
| **VERIFIED** | GitHub Actions produced it | run URL, job id, commit (Law 44) |
| **LOCAL ONLY** | a local run | labelled `NOT AUTHORITATIVE`, never a substitute |
| **EXPIRED** | source moved after the measurement | HEAD differs from the metric's commit |
| **UNMEASURED** | HEAD has no measurement | the correct thing to write instead of a stale number |

## THE TRACKER TERMS — `KNOWN_FAILURES.md`

| Token | Means |
|---|---|
| `OPEN` | the defect is present and untouched |
| `PARTIAL` | some is fixed and some is not, and the entry says which |
| `BLOCKED` | it needs a decision or an artifact somebody else owns |
| `CLOSED` | the work landed, and a mechanical predicate points at it |

## THE GATE TERMS

| Term | Definition |
|---|---|
| **exists / binds** | a gate that RUNS and a gate that BLOCKS A MERGE are different states. Only the required-status-checks list makes a gate bind |
| **mandatory gate** | one on the required list. Below its threshold → the PR is unmergeable, and it is not discussable (Law 55) |
| **done** | implementation exists · tests exist · **GitHub CI passes** · quality gates pass · mutation threshold passes · docs updated · the five progress documents updated |
| **promoted** | proven to pass on correct code AND to FAIL on deliberately broken code, then added to the required list, one at a time |

---

## ADDING A TERM

1. Notice a word that a decision depends on and that has no single meaning here.
2. **Stop. Do not pick one.** Ask the owner, with a recommended default (§E.3).
3. Record it — in `docs/ACCOUNTING_DEFINITIONS.md` if it is a product term, here if it
   is a process term.
4. Add the measurement. **A definition with no measurement is not finished** — it just
   moves the argument one level down.

## THE STANDING DEBT

The seven product terms above were load-bearing across 23 locked documents before any
of them had a measurement. That is the failure this register exists to make visible
rather than discoverable.
