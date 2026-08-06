# The Engineering Operating System

**One system. Not a pile of documents.**

This directory is the canonical home of *how engineering is done in this repository*.
`CLAUDE.md` is the bootloader that points here. `docs/` is the product architecture —
what this system IS. `engineering/` is the method — how anything here gets built.

---

## THE DESIGN DECISION, AND WHY IT IS NOT THE OBVIOUS ONE

The obvious split is **by topic**: principles, mental models, architecture,
requirements, debugging, verification. That split fails, and it fails for a measured
reason.

**A topic split does not tell you when to read the file.** So either everything is
loaded at every step — which is what already existed and already failed — or nothing
is, and the method is available but never applied.

```
MEASURED 2026-08-06, before this system existed
  CLAUDE.md                 951 lines · 9,474 words · ~13,000 tokens
  its own header            "RE-READ THIS ENTIRE FILE, EVERY TIME"
  its own §N, same file     "a long document cannot be re-run from finite
                             attention at every step, so compliance drifts
                             to 'apply what's salient'"
```

**The file diagnosed, in §N, the exact failure its own header prescribes.** That
contradiction is the root cause of this whole redesign, and no amount of better prose
inside a 951-line file could have fixed it.

So this system **splits by TRIGGER, not by topic.** Each gate document answers one
question: *what am I about to do?* The router loads only that gate, only then.

```
topic split   ->  "which file do I need?"   ->  load all, apply some, verify nothing
trigger split ->  "what am I doing?"        ->  load one, apply all, check the output
```

---

## THE LAYERS

```
LAYER 0   registry.json          machine-readable. The ONLY source of what binds when
LAYER 1   LAWS.md                the 57 laws. ONE copy. Everything else points here
LAYER 2   METHOD.md              the thinking engine — 12 stages, run in order
LAYER 3   gates/*.md             fired by trigger. Short enough to actually apply
LAYER 4   .claude/hooks/         emits LAYER 2 always, routes LAYER 3 by trigger
LAYER 5   tests/unit/            asserts LAYER 0..4 agree with each other
```

**LAYER 5 is the part that makes this different from documentation.** Before it,
`SYSTEM_LAWS.md` said "55 laws" while `CLAUDE.md` had 57, and nothing could notice.
A count that drifts teaches the reader the document is unreliable, and an unreliable
document is not consulted. The consistency test makes that drift RED.

---

## THE MAP — what exists, and when it binds

| File | Answers | Loaded |
|---|---|---|
| [`LAWS.md`](LAWS.md) | what may never be done | on demand; the 8 most-broken are always in the header |
| [`METHOD.md`](METHOD.md) | how to think about any problem | **always** — the router emits its 12 stages every turn |
| [`ANTI_PATTERNS.md`](ANTI_PATTERNS.md) | the failure this rule was born from | on demand, and when a gate cites one |
| [`DEFINITIONS.md`](DEFINITIONS.md) | what a load-bearing word means, measurably | before any work depending on the term |
| [`gates/ARCHITECTURE.md`](gates/ARCHITECTURE.md) | designing a component or boundary | writing `docs/**`, any `*ARCHITECTURE*`, `*_RULES.md` |
| [`gates/REQUIREMENTS.md`](gates/REQUIREMENTS.md) | turning a want into a SHALL | before any build; when a target is vague |
| [`gates/INVESTIGATION.md`](gates/INVESTIGATION.md) | a bug, a failure, "why is this slow" | debugging, root-cause work, `KNOWN_FAILURES.md` |
| [`gates/MEASUREMENT.md`](gates/MEASUREMENT.md) | producing or quoting a number | any metric, any claim of improvement |
| [`gates/VERIFICATION.md`](gates/VERIFICATION.md) | proving it works; the DONE GATE | writing tests, before every commit |
| [`gates/DECISION.md`](gates/DECISION.md) | choosing between options | trade-offs, tool choices, irreversible calls |
| [`registry.json`](registry.json) | which of the above binds, and where | by the hook and by the tests |

---

## THE CONTRACT — what "loaded" means

`CLAUDE.md` is the **root of precedence**, and remains the single authority. It is
short so that it is actually read. It does not contain the method; it contains the
pointer, and the pointer is enforced by a hook that runs whether or not anyone opens
the file.

```
precedence   docs/SYSTEM_INVARIANTS.md
          -> locked architecture (docs/)
          -> engineering/LAWS.md
          -> engineering/METHOD.md and gates/
          -> READMEs
LOCKS WIN.  If code and a locked doc disagree, the doc is right.
```

---

## MAINTENANCE — the three rules that keep this from rotting

1. **A rule lives in exactly one file.** Every other mention is a link. Duplication
   was the measured defect: the test-discipline rules existed in two files, Law 51 in
   four places, the mission in three. Fixing one left the others lying.
2. **A number in this directory carries the commit that produced it** (Law 56). The
   header of `LAWS.md` states the commit its count was measured at.
3. **Adding a law means adding a registry entry.** The consistency test fails
   otherwise, so the machine-readable form cannot silently fall behind the prose.

---

## WHAT THIS SYSTEM CANNOT DO — stated here, not discovered later

A hook can force the method to be **seen** and can refuse specific mechanical
violations. **It cannot make anyone reason well.** Claiming otherwise would be exactly
the unmeasured assertion this system exists to prevent.

What it removes is the failure where the method was never loaded, was loaded but too
long to apply, or was applied from a copy that had drifted from the original.
