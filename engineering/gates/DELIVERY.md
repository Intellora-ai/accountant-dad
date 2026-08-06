# GATE · DELIVERY

**Fires when:** shipping, deploying, releasing, enabling a flag — and when anything is
live and being watched.

**Gate BEFORE ship (Law 51).** Never ship or commit before the DONE GATE passes. The
gate precedes the release, never follows it.

---

0. **Gate BEFORE ship (Law 51)** — never ship or commit before the DONE GATE passes. The gate precedes the release, never follows it.
1. **Off by default → on gradually:** 1% → 10% → 30% → … → 100% of users.
2. **Canary first** — release to a small slice and watch it. Healthy → roll forward. Bad → roll back automatically.
3. **Gradual people:** a few → 10 → 100 → everyone.
4. **An undo button always exists** — one flip back to normal.
5. **Secrets in env, never in code** (Law 22).
6. **Nothing posts to a real ledger on a canary.** For this project specifically: a shipping increment that writes into someone's actual books is not a canary, it is production. Test destinations only until the number in G2 is met.

---


---

1. **Watch it live** — know before the user complains.
2. **Real honest numbers** (throughput, latency, accuracy) — **never fake** (Law 24).
3. **It screams loud** — your phone buzzes on a break; you know before users do.
4. **Heartbeat check** — green/red instantly. Is it alive?
5. **Watch the 4 signals:** **Traffic** (how many using) · **Errors** (how many failing) · **Latency** (how fast) · **Saturation** (how full).
6. **A bad number is allowed to STOP new work** until it is healthy.
7. For this project, a fifth signal: **posted-entry correctness.** A silent accuracy regression is worse than an outage — an outage is visible, a wrong entry is not.

---


---

No frozen document changes without a written amendment recording:

1. **What changed** — old rule → new rule
2. **Which doc / section**
3. **Why**
4. **What failure forced it**
5. **The trade-off** — gain vs lose
6. **The test that now guards it**
7. **Who approved + date**
8. Then resume building.

**If code and a frozen doc disagree, the doc wins and the code is wrong.** Report it. Never resolve silently in code.

---

---

## CHECKLIST

- [ ] The DONE GATE passed BEFORE this ship, not after (Law 51)
- [ ] Flag off by default; rollout is 1% → 10% → 30% → … → 100%
- [ ] Canary watched, with automatic rollback on a bad signal
- [ ] An undo button exists — one flip back to normal (Law 8)
- [ ] Secrets in env, never in code (Law 22)
- [ ] **Nothing posts to a real ledger on a canary.** Test destinations only until
      the G2 number is met
- [ ] Four signals live: traffic · errors · latency · saturation
- [ ] Fifth signal live: posted-entry correctness — a silent accuracy regression is
      worse than an outage, because an outage is visible
- [ ] A bad number is allowed to STOP new work
- [ ] If a frozen document was touched, the §M amendment is written: what changed,
      why, what failure forced it, the trade-off, the guarding test, who approved
