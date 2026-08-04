"""The Execution Engine. `ENGINE_6_EXECUTION_ENGINE_RULES.md`.

The architectural name is **Execution Engine**; the folder is `tally_engine` and
stays that way. `ENGINE_6:19` — *"Identities are part of the system contract and
are never renamed once other engines reference them."* Prose says Execution
Engine; imports say `tally_engine`; neither is a mistake.

P3 ships a stub and nothing else. `MVP_IMPLEMENTATION_BLUEPRINT.md:100`
schedules engine stubs here, `:136` permits *"no accuracy claim ... at this
phase"*, and `CLAUDE.md` §P keeps Tally posting frozen until its scheduled
phase. Real transport is P4 work and is asked for before it is written.
"""
