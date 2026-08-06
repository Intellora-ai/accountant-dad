# SYSTEM_LAWS.md

> **Pointer. Deliberately carries no law text.**

The 57 laws live in **[`engineering/LAWS.md`](engineering/LAWS.md)** — the only copy.
The 13 product invariants live in
[`docs/SYSTEM_INVARIANTS.md`](docs/SYSTEM_INVARIANTS.md), which outranks them.

**This file used to excerpt six laws and to say "55 numbered engineering laws" when
there were 57.** It was written as a convenience and became a second, wrong source.
`tests/unit/test_engineering_os.py::test_the_laws_live_in_exactly_one_file` now fails
if any law's text reappears outside `engineering/LAWS.md`, so the convenience cannot
come back.

Start here instead: **[`CLAUDE.md`](CLAUDE.md)** (the bootloader) →
[`engineering/README.md`](engineering/README.md) (the map).
