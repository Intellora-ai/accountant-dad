"""Engine 1, the Input Engine. `ENGINE_1_INPUT_ENGINE_RULES.md`.

`:24` — *"Convert raw human accounting artifacts into reliable, structured
evidence while preserving uncertainty."* It answers `:28`, *"What information
exists in the document?"*, and never `:32`, *"What does this transaction
mean?"* — meaning belongs to Engine 2.

It produces exactly one artifact, the Document Evidence Object
(`accountant_dad.artifacts.evidence`), and sends it to exactly one place:
`COMMUNICATION_RULES_INPUT_ENGINE.md:24` — *"There is no other outbound path."*

P3 ships `stub.py`, which emits that artifact and reads nothing.
"""
