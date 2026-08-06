# ENGINEERING_METHOD.md

> **Pointer. The method grew from 8 steps to 12 stages and moved.**

Canonical: **[`engineering/METHOD.md`](engineering/METHOD.md)**.

The eight steps this file used to carry are all still there — `METHOD.md` ends with a
coverage table mapping every one of them, and every mental model from `CLAUDE.md` §D,
to the stage that now holds it. `tests/unit/test_engineering_os.py::
test_every_mental_model_has_a_home` fails if one loses its home, so the merge cannot
quietly become a deletion (§E.8).

**Enforcement is unchanged and still repository-local:**
`.claude/hooks/engineering_method.py` is tracked by git and depends on no home
directory, proven by `tests/unit/test_engineering_method_enforced.py`. Its one binding
rule — a hedge refused in a truth document — still binds.

**Known limit:** `.claude/hooks/` is write-protected by the harness, so the hook still
emits the older 8-step wording, which is a strict subset of the 12 stages. `CLAUDE.md`
is the surface measured to load every session and carries the full pipeline. Recorded
in `CLAUDE.md` Amendment 5 rather than left to be discovered.
