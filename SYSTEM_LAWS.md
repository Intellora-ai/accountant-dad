# SYSTEM_LAWS.md

> **Pointer, not a copy.** The laws are in [`CLAUDE.md` §C](CLAUDE.md) — 55 numbered
> engineering laws — and the invariants in
> [`docs/SYSTEM_INVARIANTS.md`](docs/SYSTEM_INVARIANTS.md). Both predate this file and
> outrank it. Copying them here would fork the project's own constitution.

## The ones that get broken most often

| Law | |
|---|---|
| **4** | Never weaken, loosen, skip, delete or bypass a test to make code pass. Only make tests **stricter** |
| **24** | Never fabricate data, metrics, logs or results |
| **44** | **A result exists only if GitHub CI produced it.** A local pass is exploration, not evidence |
| **52** | Nothing is built until it can be measured. A vague target is a request for a number, not a requirement |
| **54** | Define universally undefined concepts before building. Never invent the definition — ask |
| **55** | A mandatory gate below its threshold makes a PR **unmergeable**. Do not ask, do not seek an exception — enter FIX MODE |

**Full text:** [`CLAUDE.md` §C](CLAUDE.md) · **Invariants:** [`docs/SYSTEM_INVARIANTS.md`](docs/SYSTEM_INVARIANTS.md)
