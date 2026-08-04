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
    "conformance_registry",  # the prohibition inventory and its negative controls
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
    "services/pipeline",  # the walking skeleton — one transaction, end to end
    "services/store",  # one state per Transaction ID (AL-INV-2)
    "services/audit",  # the append-only transition history (AL-INV-3)
}

#: Still frozen by Amendment 2, verbatim: engine reasoning · accounting logic ·
#: tax logic · AI/LLM calls · Tally posting. Matched as substrings so a module
#: cannot slip past by decorating the name.
FROZEN_MARKERS = ("engine", "accounting", "tax", "llm", "openai", "anthropic", "tally", "brain")

#: The P3 stubs, authorized by the user on 2026-08-04: *"Build src/brain/
#: skeleton. Build Engine 1-6 stubs."*
#:
#: These paths sit inside directories `FROZEN_MARKERS` covers, so they are named
#: here one by one rather than admitted by a pattern. `BLUEPRINT:100` schedules
#: engine stubs at P3 and `:99` schedules the Brain stub at P3; `:86` — the stub
#: *"proves the seam without knowledge. Engines call it and it answers
#: structurally; nothing is faked as accounting truth."*
#:
#: An exhaustive list, not a rule, because the exhaustive form is the one that
#: makes a seventh engine or a second brain module VISIBLE. A pattern like
#: "anything called stub.py" would admit code nobody reviewed.
#:
#: `engines/tally_engine` keeps that name deliberately: `ENGINE_6:19` — the
#: architectural name is Execution Engine, the folder is locked and *"identities
#: are part of the system contract and are never renamed once other engines
#: reference them."*
#: CLAUDE.md §P, **Amendment 3** — Engine 1 authorization, approved 2026-08-05.
#: *"Engine 1, and only Engine 1, is released for implementation… Nothing outside
#: Engine 1 is authorized by this amendment."*
#:
#: Exhaustive, like `AUTHORIZED_STUBS` and for the same reason: an exhaustive
#: list makes a seventh sub-engine VISIBLE, where a pattern such as "anything
#: under input_engine" would admit code nobody reviewed.
#:
#: `SUB_ENGINE_RESPONSIBILITIES.md` §1 names exactly four sub-engines — `cleaner`,
#: `reader`, `parser`, `confidence` — and states: *"No assembler sub-engine
#: exists, and none may be added."* The parent Input Engine performs the assembly
#: itself, so `assembly` here is the ENGINE's own work, not a fifth sub-engine.
ENGINE_1_AUTHORIZED = {
    "engines/input_engine/cleaner",  # §1.1 deskew · denoise · crop · contrast
    "engines/input_engine/reader",  # §1.2 text extraction, per-region confidence
    "engines/input_engine/parser",  # §1.3 structure and tables, never meaning
    "engines/input_engine/confidence_report",  # §1.4 "was this read correctly?"
    "engines/input_engine/classification",  # document classification (Amendment 3)
    "engines/input_engine/config",  # every threshold, named — no hardcoded value
    "engines/input_engine/measurement",  # the calibration record
    "engines/input_engine/assembly",  # the ENGINE assembles; not a sub-engine
}

AUTHORIZED_STUBS = {
    "brain/__init__",
    "brain/stub",
    "engines/__init__",
    "engines/input_engine/__init__",
    "engines/input_engine/stub",
    "engines/understanding_engine/__init__",
    "engines/understanding_engine/stub",
    "engines/accounting_engine/__init__",
    "engines/accounting_engine/stub",
    "engines/clarification_engine/__init__",
    "engines/clarification_engine/stub",
    "engines/validation_engine/__init__",
    "engines/validation_engine/stub",
    "engines/tally_engine/__init__",
    "engines/tally_engine/stub",
}


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
    unlisted = sorted(
        package_modules() - PERMITTED_MODULES - AUTHORIZED_STUBS - ENGINE_1_AUTHORIZED
    )
    assert unlisted == [], (
        f"module(s) not on the Amendment 2 permitted list: {unlisted}. "
        "Add the name here deliberately, or the freeze was crossed by accident."
    )


def test_no_module_belongs_to_a_still_frozen_category() -> None:
    offenders = frozen_named(package_modules() - AUTHORIZED_STUBS - ENGINE_1_AUTHORIZED)
    assert offenders == [], (
        f"module(s) named for a still-frozen category: {offenders}. Engine "
        "reasoning for Engines 2-6, accounting logic, tax logic, AI calls and "
        "Tally posting stay frozen until their scheduled phase (CLAUDE.md §P)."
    )


def test_engine_1_authorization_admits_only_the_input_engine() -> None:
    """Amendment 3 released ONE engine. This is what keeps it to one.

    The amendment's own words are *"Nothing outside Engine 1 is authorized by
    this amendment."* Without this test `ENGINE_1_AUTHORIZED` becomes the next
    place to park anything — adding `engines/accounting_engine/rules` would sail
    straight past both tests above, exactly as `AUTHORIZED_STUBS` would have.
    """
    trespassers = sorted(
        name for name in ENGINE_1_AUTHORIZED if not name.startswith("engines/input_engine/")
    )
    assert trespassers == [], (
        f"ENGINE_1_AUTHORIZED names path(s) outside Engine 1: {trespassers}. "
        "Amendment 3 released Engine 1 and nothing else; releasing another "
        "engine takes its own amendment (§M), not an edit to this list."
    )


def test_engine_1_authorization_never_admits_accounting_reasoning() -> None:
    """*"No accounting reasoning is permitted inside Engine 1."* — Amendment 3.

    Engine 1 reads a document. Deciding what the document MEANS is Engine 2, and
    deciding the entry is Engine 3 — which `TECHNOLOGY_STACK.md` requires to be
    deterministic and LLM-free precisely so the entry is defensible. A module
    named for accounting, tax, an LLM vendor, the Brain or Tally inside Engine 1
    is that boundary being crossed under cover of a released engine.
    """
    inside_engine_1 = {name.removeprefix("engines/input_engine/") for name in ENGINE_1_AUTHORIZED}
    reasoning = sorted(
        name for name in inside_engine_1 if any(marker in name.lower() for marker in FROZEN_MARKERS)
    )
    assert reasoning == [], (
        f"Engine 1 module(s) named for reasoning that is not Engine 1's: {reasoning}. "
        "Engine 1 reads; it never decides what a document means or what to post."
    )


def test_the_other_five_engines_remain_frozen() -> None:
    """Amendment 3 is narrow, and narrow is only true if it is checked.

    Engines 2-6 may carry their `__init__` and their P3 `stub` and nothing more.
    """
    siblings = {
        "understanding_engine",
        "accounting_engine",
        "clarification_engine",
        "validation_engine",
        "tally_engine",
    }
    escaped = sorted(
        name
        for name in package_modules() - AUTHORIZED_STUBS
        if any(name.startswith(f"engines/{sibling}/") for sibling in siblings)
    )
    assert escaped == [], (
        f"module(s) in a still-frozen engine: {escaped}. Amendment 3 released "
        "Engine 1 only. Engines 2-6 keep their __init__ and their P3 stub until "
        "each is asked for and amended in writing."
    )


def test_the_stub_allowlist_admits_only_stubs_and_only_where_stubs_belong() -> None:
    """The list is the hole, so the list is what gets constrained.

    Without this, `AUTHORIZED_STUBS` is a place to park anything: adding
    `engines/accounting_engine/tax_rules` would sail past both tests above and
    put tax logic in the package while the freeze still covers it.

    Two constraints, both structural. A stub lives under `engines/` or `brain/`,
    and it is called `stub` or `__init__` — nothing else. `stub.py` is where
    `BLUEPRINT:86` puts a thing that "answers structurally" without knowledge;
    a file called anything else is claiming to do something a stub does not.
    """
    misplaced = sorted(
        name for name in AUTHORIZED_STUBS if not (name.startswith(("engines/", "brain/")))
    )
    assert misplaced == [], (
        f"outside engines/ and brain/: {misplaced}. The stub allowlist exists "
        "for the two directories the freeze covers, not as a general exemption."
    )

    not_a_stub = sorted(
        name for name in AUTHORIZED_STUBS if name.rsplit("/", 1)[-1] not in {"stub", "__init__"}
    )
    assert not_a_stub == [], (
        f"not a stub: {not_a_stub}. A stub is `stub.py` or a package `__init__`. "
        "Anything else is engine reasoning, which CLAUDE.md §P still freezes."
    )


def test_the_stub_allowlist_covers_six_engines_and_one_brain() -> None:
    """Six engines, no more (`ENGINE_2:307` — do not add new sub-engines; the
    same rule holds at engine level). A seventh entry here is an architecture
    change wearing a test edit."""
    engine_dirs = {
        name.split("/")[1]
        for name in AUTHORIZED_STUBS
        if name.startswith("engines/") and name.count("/") > 1
    }
    assert engine_dirs == {
        "input_engine",
        "understanding_engine",
        "accounting_engine",
        "clarification_engine",
        "validation_engine",
        # ENGINE_6:19 — architectural name Execution Engine, folder locked.
        "tally_engine",
    }
    assert {name for name in AUTHORIZED_STUBS if name.startswith("brain/")} == {
        "brain/__init__",
        "brain/stub",
    }


def test_an_authorized_stub_is_never_also_on_the_permitted_list() -> None:
    """Two lists granting the same path would let one quietly outlive the other
    when the stubs are replaced by real engines at P4."""
    assert not AUTHORIZED_STUBS & PERMITTED_MODULES


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
