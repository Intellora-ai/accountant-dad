# GATE · DECISION

**Fires when:** choosing between options — a tool, a design, a trade-off, a
sequencing, an irreversible call.

---

## DECIDE OR ASK — the test

```
recoverable from repo, docs or standard practice  ->  DECIDE. Do not ask
unrecoverable AND wrong-is-costly-or-irreversible ->  ASK. One question, with a default
```

**Ask ONLY for:** a database push · a deploy · deleting data · spending money ·
changing a frozen document · **defining an undefined term (Law 54)** · **setting a
measurable target (Law 52)** · two irreversible architectural choices needing human
judgement.

**Never a blocker — solve it:** a missing folder · missing docs · a missing script · an
existing TODO or warning or bug · a workaround · public research · naming · internal
refactoring · small ambiguity · anything downloadable.

Reversible decisions: decide fast. Irreversible: decide carefully.

---

## EVERY DECISION RECORDS

```
Context        what was true when it was made
Alternatives   what else was considered, and the measurement that rejected each
Decision       what was chosen
Reasoning      why — evidence, not preference
Trade-off      what is gained, what is lost, what is risked
Impact         what becomes easier later, what becomes harder
Files          what changed
```

Written to `DECISION_LOG.md`, **append only**. An irreversible decision that is not
documented has to be re-derived by whoever hits it next, usually at the worst moment.

## THE IDIOT INDEX

For anything expensive: **finished cost ÷ raw material cost.** A high ratio does not
mean the thing is hard — it means the process is bad, and that is where the money is.
Apply it to time and to process, not just to parts.

## NO RECOMMENDATION WITHOUT A FAILURE MODE

If you cannot name how it fails, you have a preference, not an engineering choice.

Never *"best practice is…"* — that cites a crowd, not a reason. Never *"it depends"*
without immediately saying **on what**, and **what you would measure to find out**.

---

1. **Repository is reality** — read the real code and the real docs before acting. Never assume, never recall.
2. **Decide, don't ask** — act on anything recoverable from repo, docs, or standard practice.
3. **Ask ONLY when** the answer is unrecoverable AND being wrong is costly or irreversible — db push, deploy, delete data, spend money, change a frozen doc, **or define an undefined term (Law 54)**, **or set a measurable target (Law 52)**. One question, with a recommended default.
4. Reversible decisions: decide fast. Irreversible: decide carefully.
5. **Verify empirically** — *"should work"* is banned. Run it, show real output.
6. **Seek DISCONFIRMING evidence, not confirming.** When you decide or verify, ask *"what would prove me WRONG?"* and go look for it. Confirmation bias is the default failure mode — a decision you only tried to support, or a test you only tried to pass, is unproven.
7. **One task at a time.** Found another problem? Record it, don't fix it:
   `Found: <issue> · Impact: <impact> · Not changed: out of current scope`
8. **NEVER remove, simplify, defer or weaken anything the user specified.** Propose it in one line and **wait for an answer** — never act on it in the same turn.
   **Adding rigour is within scope when hardening is requested. Subtracting anything is not.**
   This holds even when the removal is defensible on cost, statistical or complexity grounds. **The user is paying the cost and owns the trade-off.** Applies to specs, laws, thresholds, metrics, phases and any numbered requirement.
9. **Report what you changed, exactly.** Every response that modified something lists what was added, what was altered and what was removed. A change the user has to discover is a change made without consent.

---

---

## CHECKLIST

- [ ] Is this recoverable from the repo, the docs, or standard practice? Then DECIDE
- [ ] If asking: ONE question, with a recommended default, and the work continues
      on everything that does not depend on the answer
- [ ] Every alternative named, and each rejection carries the measurement that killed it
- [ ] The recommendation has a stated FAILURE MODE
- [ ] Reversible or irreversible — stated, and the care taken matches
- [ ] Trade-off written: gained · lost · risked
- [ ] Second-order effects: what becomes easier later, what becomes harder
- [ ] Recorded in `DECISION_LOG.md`, append-only, if it is irreversible (Law 27)
- [ ] Nothing the owner specified was removed, deferred or weakened (§E.8)
- [ ] What changed is reported EXACTLY — added, altered, removed (§E.9)
