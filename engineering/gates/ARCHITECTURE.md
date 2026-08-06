# GATE · ARCHITECTURE

**Fires when:** designing a component, a boundary, an artifact, or a contract.
Writing anything under `docs/`, any `*ARCHITECTURE*`, any `*_RULES.md`, any
`*_SPEC.md`. Also whenever a change would alter what a component is ALLOWED to be.

**Read [`../METHOD.md`](../METHOD.md) first.** This gate is what the method produces
when the subject is a boundary. It does not replace the thinking; it records it.

---

## THE ORDER, AND IT IS NOT OPTIONAL

```
WHY  (need)      ->  WHAT (requirement)  ->  HOW (architecture)  ->  implementation
```

Never HOW → WHY. A design that starts from a solution has already chosen its
requirements, and nobody will ever see which ones it silently rejected.

```
Architecture   (what it is ALLOWED to be)      -> owner approves -> FROZEN
      v
Blueprint      (what gets built, in what order) -> owner approves
      v
Build -> Verify -> Fix   (per phase, until green)
      v
DONE GATE      (stated, before every commit)
```

**Code that arrives before its blueprint is unscoped work and gets reverted.**

---

**Purpose:** define what the build is *allowed to be*. Not what it does — what it may and may not be. Written by Claude, **approved by the user**, then frozen. After freezing it changes only by amendment (§M).

**If code and the architecture disagree, the architecture wins and the code is wrong.** Report it; never resolve silently in code.

Every architecture document contains, in this order:

### G1. Mission
What this build exists to achieve, in one sentence. If it takes two, the build is two builds.

### G2. Measurable finish line (Law 52)
The number that decides whether this build succeeded. One number. With a unit. Agreed with the user **before** the architecture is approved.

*Not:* "accurate extraction." *Yes:* "≥ 95% field-level extraction accuracy on typed invoices, measured against human re-keying of 10 documents."

### G3. Undefined terms, defined (Law 54)
Every term this build depends on that has no universal definition, listed and **defined here with its measurement**. If a term cannot be defined, the build does not start. Never invent the definition — ask.

### G4. Components and ownership
Every component, what it owns, and **exactly one owner per concept.** No responsibility appears twice. No component owns two problems.

### G5. Boundaries — what each component may never do
Absolute prohibitions, stated per component. These become the predicates that get enforced later.

### G6. Contracts — what crosses each boundary
Every arrow carries exactly one named artifact. For each boundary, all nine items: input artifact · output artifact · creator · owner · allowed transformation · forbidden transformation · decision authority · uncertainty movement · failure movement.

### G7. Invariants
Statements that are always true, at every moment, for every transaction. Ranked by precedence. **Locks win** — a newer document never silently changes a locked one; it is revised instead.

### G8. Failure behaviour
What happens when each component cannot complete. **Never fabricate output. Never continue with partial reasoning.** What is preserved, what is reported, where it can restart.

### G9. What this build deliberately does NOT include
Non-goals, explicit. The most valuable section — it is what stops scope creep from being arguable.

### G10. Forward Dependency Inventory
Before locking, list **every promise already made about this component by anything already locked.** Each is honoured or explicitly revised with the contradiction named. **A promise that is neither honoured nor revised is a defect, not a choice.** Conflicts are resolved *before* writing, never during propagation.

### G11. Freeze and amendment
Stated freeze date. Amendment process per §M.

---


---

## CHECKLIST — every line stated, ✓ or N/A with the reason

- [ ] **G1 Mission** — one sentence. Two sentences means two builds
- [ ] **G2 Finish line** — ONE number, with a unit, agreed with the owner BEFORE approval
- [ ] **G3 Undefined terms** — every load-bearing word defined with its measurement,
      registered in [`../DEFINITIONS.md`](../DEFINITIONS.md). Never invent one — ask
- [ ] **G4 Ownership** — exactly one owner per concept. No responsibility appears twice
- [ ] **G5 Boundaries** — what each component may NEVER do, as absolutes
- [ ] **G6 Contracts** — one named artifact per arrow, all nine items
- [ ] **G7 Invariants** — ranked by precedence. Locks win
- [ ] **G8 Failure behaviour** — never fabricate, never continue on partial reasoning
- [ ] **G9 Non-goals** — the section that makes scope creep unarguable
- [ ] **G10 Forward dependencies** — every promise already made about this component by
      anything already locked, honoured or explicitly revised. **A promise neither
      honoured nor revised is a defect, not a choice**
- [ ] **G11 Freeze date + amendment process** (§M)
- [ ] **Inversion applied** — "how would I design this to fail forever?" and the
      answers designed against
- [ ] **Systems** — what information must flow across this boundary, and what must
      NEVER flow across it
- [ ] **Future** — if this ships, what breaks next?
- [ ] **Simpler** — can a component be removed? Can two become one?
- [ ] **Equivalent easier problem** — was the hard problem transformed, or attacked?
      (Law 53)

**If any line cannot be ticked, the architecture is not ready to approve.**
