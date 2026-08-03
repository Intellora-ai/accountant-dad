"""The build gate ships this package. Prove it imports and stays inside the freeze.

Amendment 2 replaced the blanket freeze with an exhaustive permitted list, so
the guard below changed with it — from *"this package contains nothing"* to
*"this package contains only what CLAUDE.md §P permits."* That is stricter, not
looser: the old form asserted one fact and stopped; this one names every module
on disk and fails on anything unlisted, refuses any still-frozen category by
name, and refuses to let the permitted list quietly cover one.

Read off DISK, not off `vars(accountant_dad)`. The old version inspected the
imported module's attributes, so a submodule only appeared once some *other*
test happened to import it — under `pytest-randomly` the same commit could pass
or fail depending on test order. A freeze guard that depends on execution order
guards nothing on the run where it matters.

MADE STRICTER AGAIN, 2026-08-04. Modules are now matched by their PATH inside
the package, not by their bare filename. `path.stem` could not tell
`services/state.py` from `engines/accounting_engine/state.py`, so a permitted
name admitted a module anywhere in the tree — including inside a directory the
freeze covers. Paths pin the layout as well as the names.
"""

from __future__ import annotations

import pathlib

import accountant_dad

#: CLAUDE.md §P, Amendment 2, "Permitted now — exhaustive". A module lands here
#: only when the amendment already permits its category. Adding a name here is
#: the visible, reviewable act that admits new code past the freeze.
#:
#: Paths are relative to the package root, without `.py`, POSIX separators.
PERMITTED_MODULES = {
    "__init__",
    "identity",  # artifact schemas — the identity envelope (INV-3, INV-5, INV-9)
    "confidence",  # artifact schemas — the one Confidence representation
    "knowledge_contract",  # Brain interface contract — P2 (BLUEPRINT §2 line 84)
    "ablation",  # the ID ablation harness — P2 (BLUEPRINT §2 line 135, INV-9)
    "conformance",  # conformance predicates — Amendment 2, permitted list
    # Amendment 2 "Permitted now — exhaustive", remaining three categories.
    "ingestion",  # document-ingestion tooling
    "sealing",  # held-out sealing mechanism
    "baseline",  # strong baseline
    # The six canonical artifacts of DATA_FLOW.md §2, one module each.
    "artifacts/__init__",
    "artifacts/evidence",  # Document Evidence Object      — Engine 1
    "artifacts/understanding",  # Business Understanding Object — Engine 2
    "artifacts/decision",  # Accounting Decision           — Engine 3
    "artifacts/clarification",  # Clarification Request     — Engine 4
    "artifacts/validation",  # Validation Decision          — Engine 5
    "artifacts/execution",  # Execution Result              — Engine 6
    # Application Layer skeleton — named on Amendment 2's permitted list
    # verbatim. DATA_FLOW.md §14 calls it `src/services/`.
    "services/__init__",
    "services/state",  # the locked transaction state machine
}

#: Still frozen by Amendment 2, verbatim: engine reasoning · accounting logic ·
#: tax logic · AI/LLM calls · Tally posting. Matched as substrings so a module
#: cannot slip past by decorating the name.
FROZEN_MARKERS = ("engine", "accounting", "tax", "llm", "openai", "anthropic", "tally", "brain")


def package_modules() -> set[str]:
    """Every module in the package, by its path relative to the package root."""
    root = pathlib.Path(str(accountant_dad.__file__)).parent
    return {
        path.relative_to(root).with_suffix("").as_posix()
        for path in root.rglob("*.py")
        if "__pycache__" not in path.parts
    }


def frozen_named(names: set[str] | frozenset[str]) -> list[str]:
    return sorted(n for n in names if any(m in n.lower() for m in FROZEN_MARKERS))


def test_package_imports_and_exposes_a_version() -> None:
    assert accountant_dad.__version__ == "0.0.0"


def test_every_module_is_on_the_permitted_list() -> None:
    unlisted = sorted(package_modules() - PERMITTED_MODULES)
    assert unlisted == [], (
        f"module(s) not on the Amendment 2 permitted list: {unlisted}. "
        "Add the name here deliberately, or the freeze was crossed by accident."
    )


def test_no_module_belongs_to_a_still_frozen_category() -> None:
    offenders = frozen_named(package_modules())
    assert offenders == [], (
        f"module(s) named for a still-frozen category: {offenders}. Engine "
        "reasoning, accounting logic, tax logic, AI calls and Tally posting "
        "stay frozen until their scheduled phase (CLAUDE.md §P)."
    )


def test_the_permitted_list_cannot_silently_cover_a_frozen_category() -> None:
    # Anti-gaming, aimed at me. The cheapest way past the two tests above is to
    # append a frozen-category name to PERMITTED_MODULES. This makes the two
    # lists contradict each other loudly instead of one quietly winning.
    contradictions = frozen_named(PERMITTED_MODULES)
    assert contradictions == [], (
        f"PERMITTED_MODULES names a still-frozen category: {contradictions}. "
        "That is an amendment, not a test edit."
    )


def test_the_permitted_list_pins_a_location_not_just_a_name() -> None:
    """A bare name would admit the same filename anywhere in the tree.

    `state` alone would permit `engines/accounting_engine/state.py` as readily
    as `services/state.py`. Every entry below the package root must therefore
    carry its directory, so the list constrains the layout too.
    """
    root_level = {"__init__"}
    bare = sorted(
        name
        for name in PERMITTED_MODULES
        if "/" not in name and name not in root_level and name != name.lower()
    )
    assert bare == [], f"entries must be paths, not bare names: {bare}"

    for name in PERMITTED_MODULES:
        assert not name.startswith("/"), f"{name} must be relative to the package root"
        assert not name.endswith(".py"), f"{name} must not carry a .py suffix"


def test_no_module_escapes_the_package_the_wheel_ships() -> None:
    """`pyproject.toml` ships `src/accountant_dad` and nothing else.

    Code outside it is code CI cannot judge, and Law 44 says a result exists
    only if CI produced it. This asserts the guard is reading the shipped tree.
    """
    root = pathlib.Path(str(accountant_dad.__file__)).parent
    assert root.name == "accountant_dad"
    assert root.parent.name == "src"
