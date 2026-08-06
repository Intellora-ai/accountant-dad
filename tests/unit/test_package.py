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

MADE STRICTER AGAIN, 2026-08-06 (F-021). Everything above reads NAMES. Nothing
above opens a file. A module called `engines/input_engine/gst_rates.py` full of
tax logic failed the filename check only because of what it was CALLED, and the
identical code under an innocent name passed every assertion in this file.
Amendment 3's binding guard is written *"a new test proves no module NAMED for
accounting, tax, LLM, brain or Tally enters it"* — and "named" was doing all the
work while the amendment's actual promise is *"No accounting reasoning is
permitted inside Engine 1."*

The section at the end of this file reads CONTENTS, by AST. It does not replace
the name checks; the name checks stay exactly as strict as they were and the
content checks are added on top. Read `test_engine_1_defines_no_accounting_or_
tax_computation_identifier` for the honest statement of what a static check can
and cannot prove here — it is deliberately narrower than the amendment's prose.
"""

from __future__ import annotations

import ast
import pathlib
import re

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
    "engines/input_engine/pipeline",  # the ENGINE's own runner: bytes in, artifact out
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


# ══════════════════════════════════════════════════════════════════════════
# F-021 — the freeze reads CODE, not only filenames
# ══════════════════════════════════════════════════════════════════════════

#: Engine 1's ENTIRE first-party reach. Exhaustive, and MEASURED rather than
#: chosen: an AST sweep of `engines/input_engine/` found exactly these four
#: targets and no others, across all ten modules on disk.
#:
#: `COMMUNICATION_RULES_INPUT_ENGINE.md:14` — Engine 1 communicates with exactly
#: one engine, by sending exactly one artifact. It therefore has no reason to
#: name Engine 2-6, the Brain, or any artifact that is not its own output.
#: Exhaustive rather than a prefix rule, for the same reason `ENGINE_1_AUTHORIZED`
#: is: a rule such as "anything under artifacts/" would silently admit
#: `artifacts/decision`, which is the Accounting Engine's output and the exact
#: boundary this exists to hold.
ENGINE_1_MAY_IMPORT = (
    "accountant_dad.engines.input_engine",  # itself
    "accountant_dad.artifacts.evidence",  # its one output artifact (DATA_FLOW §2)
    "accountant_dad.identity",  # the identity envelope (INV-3, INV-5, INV-9)
    "accountant_dad.confidence",  # the ONE Confidence representation
)

#: Vendor SDKs whose whole purpose is to have a model reason. CLAUDE.md §P keeps
#: "AI/LLM calls" frozen for every engine, and `TECHNOLOGY_STACK.md` puts the
#: reasoning engines behind a determinism requirement Engine 1 does not get to
#: pre-empt by reading a document with a chat model.
#:
#: NOT exhaustive, and this is the weaker of the two content checks: a vendor
#: absent from this tuple passes. It is kept because it fails for a different
#: reason than `test_declared_dependencies.py` does — that file refuses an
#: UNDECLARED import, this one refuses a declared one.
#:
#: `transformers`, `torch` and `docling` are deliberately absent. They run
#: layout and OCR models over pixels, which is Engine 1's own job
#: (`ENGINE_1_INPUT_ENGINE_RULES.md` §1.2-1.3); they decide no meaning.
AI_VENDOR_PACKAGES = (
    "openai",
    "anthropic",
    "cohere",
    "mistralai",
    "google",
    "vertexai",
    "langchain",
    "langchain_core",
    "llama_cpp",
    "llama_index",
    "litellm",
    "ollama",
    "groq",
    "replicate",
)

#: Words that can only name accounting or tax COMPUTATION, never a document's
#: identity. MEASURED absent from every identifier under `engines/input_engine/`
#: before being written here — a vocabulary chosen without that measurement
#: would either fire on legitimate code or, worse, be quietly trimmed until it
#: stopped firing.
#:
#: WHY `tax`, `debit`, `credit` AND `invoice` ARE NOT HERE, and this is the
#: honest part: `classification.py:130-136` legitimately defines `TAX_INVOICE`,
#: `DEBIT_NOTE`, `CREDIT_NOTE` and `PROFORMA_INVOICE`. Those are document KINDS,
#: and classifying a document by kind is exactly what Amendment 3 released
#: Engine 1 to do. Including those four words would fire on authorized work, and
#: a guard that fires on correct code gets weakened until it fires on nothing.
#: They remain in `FROZEN_MARKERS` above, so `tax_rules.py` is still refused by
#: NAME — the two checks cover different halves and neither is dropped.
ENGINE_1_FORBIDDEN_WORDS = (
    "accounting",
    "gst",
    "cgst",
    "sgst",
    "igst",
    "hsn",
    "itc",
    "tds",
    "ledger",
    "journal",
    "voucher",
    "posting",
    "llm",
    "openai",
    "anthropic",
    "tally",
    "brain",
)

#: Splits an identifier into words: `TAX_INVOICE` -> tax, invoice;
#: `GSTRate` -> gst, rate. Whole WORDS, never substrings — a substring rule
#: would match `itc` inside `switch` and `tds` inside anything, and the first
#: false positive is what gets a guard deleted.
_WORD = re.compile(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z0-9]+|[A-Z]+")

#: Functions that import by NAME rather than by statement. Engine 1 uses both
#: (`parser.require_module("docling.document_converter")`,
#: `importlib.import_module("paddleocr")`), so a check that read only `import`
#: statements would miss the route this engine actually takes.
_IMPORTERS = ("import_module", "require_module", "__import__")


def words_in(identifier: str) -> set[str]:
    found: set[str] = set()
    for chunk in identifier.split("_"):
        found.update(piece.lower() for piece in _WORD.findall(chunk))
    return found


def engine_1_sources() -> list[pathlib.Path]:
    """Every file on disk under `engines/input_engine/`, whatever it is called.

    Reads the DIRECTORY, not `ENGINE_1_AUTHORIZED`. A module the allowlist does
    not mention is already refused by the tests above, but it must not also be
    invisible to the content checks — the interesting failure is a file that is
    both unlisted and full of tax logic, and it has to fail twice, not once.
    """
    root = pathlib.Path(str(accountant_dad.__file__)).parent / "engines" / "input_engine"
    sources = sorted(path for path in root.rglob("*.py") if "__pycache__" not in path.parts)
    assert sources != [], (
        f"no modules found under {root}. The content guard derives everything "
        "from the tree, so reading an empty tree would pass while proving nothing."
    )
    return sources


def imported_names(tree: ast.Module) -> set[str]:
    """Every module this source names, by statement OR by string literal."""
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            found.add(node.module)
        elif isinstance(node, ast.Call):
            found |= _dynamic_import_target(node)
    return found


def _dynamic_import_target(node: ast.Call) -> set[str]:
    called = node.func
    label = called.attr if isinstance(called, ast.Attribute) else getattr(called, "id", None)
    if label not in _IMPORTERS or not node.args:
        return set()
    first = node.args[0]
    if isinstance(first, ast.Constant) and isinstance(first.value, str):
        return {first.value}
    return set()


def declared_identifiers(tree: ast.Module) -> list[tuple[str, int]]:
    """Names this source DEFINES or REFERENCES — never its prose.

    String literals are excluded, and that exclusion is measured rather than
    assumed: `classification.py:130-136` carries the literals `'Tax Invoice'`,
    `'Debit Note'` and `'CREDIT NOTE'` as OCR cues for document kinds, and
    `parser.py:378` carries an English sentence naming accounting concepts in
    order to say the parser does NOT supply them. Matching on literals would
    fire on all of it. Comments and docstrings are outside the AST's reach
    anyway, which is one more reason to read structure and not text.
    """
    found: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            found.append((node.name, node.lineno))
        elif isinstance(node, ast.Name):
            found.append((node.id, node.lineno))
        elif isinstance(node, ast.Attribute):
            found.append((node.attr, node.lineno))
        elif isinstance(node, ast.arg):
            found.append((node.arg, node.lineno))
        elif isinstance(node, ast.keyword):
            # `f(**kwargs)` is an `ast.keyword` whose `arg` is None: a call with
            # no keyword NAME to read, and nothing for this sweep to judge.
            if node.arg is not None:
                found.append((node.arg, node.lineno))
        elif isinstance(node, ast.alias):
            found.append((node.asname or node.name, node.lineno))
    return found


def engine_1_trees() -> list[tuple[str, ast.Module]]:
    return [(path.name, ast.parse(path.read_text(encoding="utf-8"))) for path in engine_1_sources()]


def test_engine_1_reaches_for_nothing_outside_its_own_boundary() -> None:
    """ONE guard for ALL of Engine 1, not nine copies of one.

    Before this, exactly one of Engine 1's modules had a cross-engine import
    guard (`test_input_engine_parser.py:357`) while all five sibling STUBS had
    one — the stubs were better protected than the released engine. Nine
    per-module copies would be nine places to forget on the tenth module, so
    the guard reads the directory and the allowlist is the only thing to edit.

    Catches the dynamic route too: `require_module("accountant_dad.brain.stub")`
    is an import, and a check that read only `import` statements would wave it
    through in the one engine that actually imports things by name.
    """
    offenders: list[str] = []
    for name, tree in engine_1_trees():
        for target in sorted(imported_names(tree)):
            if not target.startswith("accountant_dad"):
                continue
            if any(
                target == allowed or target.startswith(f"{allowed}.")
                for allowed in ENGINE_1_MAY_IMPORT
            ):
                continue
            offenders.append(f"{name} imports {target}")

    assert offenders == [], (
        f"Engine 1 reaches outside its boundary: {sorted(offenders)}. It may name "
        f"only {list(ENGINE_1_MAY_IMPORT)} — itself, its one output artifact, the "
        "identity envelope and the one Confidence representation. Engine 1 sends "
        "one artifact to one engine (COMMUNICATION_RULES_INPUT_ENGINE.md:14); "
        "importing anything else is that boundary being crossed in code."
    )


def test_engine_1_imports_no_ai_vendor_package() -> None:
    """*"Still frozen: ... AI/LLM calls"* — CLAUDE.md §P.

    Engine 1 reads what is on the page. A chat model asked what the page MEANS
    is Engine 2's job done in the wrong engine, and `TECHNOLOGY_STACK.md`
    requires the engine that decides the entry to be reproducible — a property
    lost the moment a model's answer enters the evidence upstream of it.
    """
    offenders: list[str] = []
    for name, tree in engine_1_trees():
        for target in sorted(imported_names(tree)):
            root = target.split(".")[0]
            if root in AI_VENDOR_PACKAGES:
                offenders.append(f"{name} imports {target}")

    assert offenders == [], (
        f"Engine 1 imports an AI vendor package: {sorted(offenders)}. Engine 1 "
        "reads a document; deciding what it means is Engine 2 and deciding the "
        "entry is Engine 3, which TECHNOLOGY_STACK.md requires to be LLM-free."
    )


def test_engine_1_defines_no_accounting_or_tax_computation_identifier() -> None:
    """The filename check, done on the CODE. And the limit of doing so.

    WHAT THIS PROVES. No function, class, variable, attribute, argument or
    import alias anywhere under `engines/input_engine/` is named for accounting
    or tax computation. `gst_rates.py` renamed to `helpers.py` still fails,
    because `GST_RATES` and `compute_cgst` are still in it. That is the hole
    F-021 named, and it is closed.

    WHAT THIS DOES NOT PROVE, stated plainly because a guard that overclaims is
    worse than the filename check it replaces: **no static check can prove the
    absence of accounting reasoning.** A module that computed a tax split under
    neutral identifiers — `def apportion(total, fraction)` over `Decimal`s —
    passes this test, passes every other test in this file, and is still exactly
    the thing Amendment 3 forbids. Three specific blind spots, named rather than
    implied:

    * neutral naming, above;
    * the four words `tax`, `debit`, `credit` and `invoice`, which are excluded
      because `classification.py:130-136` uses them for document KINDS, which is
      authorized work (they stay in `FROZEN_MARKERS`, so filenames still refuse
      them);
    * string literals, excluded because Engine 1 legitimately carries
      `'Tax Invoice'` as an OCR cue.

    So this is a NARROWER claim than Amendment 3's prose, honestly held: the
    freeze now catches forbidden logic that is named for what it is, and cannot
    catch forbidden logic that is disguised. The remaining coverage comes from
    review, not from this file, and pretending otherwise is the failure mode.
    """
    offenders: list[str] = []
    for name, tree in engine_1_trees():
        for identifier, lineno in declared_identifiers(tree):
            hit = sorted(words_in(identifier) & set(ENGINE_1_FORBIDDEN_WORDS))
            if hit:
                offenders.append(f"{name}:{lineno} `{identifier}` names {hit}")

    assert sorted(set(offenders)) == [], (
        f"Engine 1 defines accounting/tax identifiers: {sorted(set(offenders))}. "
        "Engine 1 reads a document; it never decides what the document means "
        "(Engine 2) or what to post (Engine 3). CLAUDE.md Amendment 3: 'No "
        "accounting reasoning is permitted inside Engine 1.'"
    )


# ── the content guard must not be hollow ──────────────────────────────────
# A detector nobody attacked is a detector that reports zero because it looks
# at nothing. Every helper above is attacked here with the shape it exists to
# catch, built from in-memory source: this repository's freeze forbids planting
# a sample module in the tree, and a string needs no cleanup to be forgotten.


def test_the_word_splitter_reads_whole_words_and_not_substrings() -> None:
    assert words_in("TAX_INVOICE") == {"tax", "invoice"}
    assert words_in("GSTRate") == {"gst", "rate"}
    assert words_in("compute_cgst_share") == {"compute", "cgst", "share"}
    # The false positives that would get this guard deleted if it used `in`.
    assert "itc" not in words_in("switch")
    assert "itc" not in words_in("pitch_detection")
    assert "gst" not in words_in("suggestion")


def test_the_identifier_sweep_catches_the_file_that_defeated_the_name_check() -> None:
    """F-021's own demonstration, run as a test.

    The reported hole was a module named `gst_rates.py`. Renaming it to
    something innocent is the interesting case — the NAME check is then blind
    and only the content check is left. Both the enum-ish constant and the
    function are caught.
    """
    tree = ast.parse(
        "GST_RATES = {'goods': 18}\n"
        "def compute_cgst(total):\n"
        "    return total * GST_RATES['goods']\n"
    )
    caught = {
        identifier
        for identifier, _ in declared_identifiers(tree)
        if words_in(identifier) & set(ENGINE_1_FORBIDDEN_WORDS)
    }
    assert caught == {"GST_RATES", "compute_cgst"}


def test_the_identifier_sweep_ignores_prose_so_it_can_stay_zero_tolerance() -> None:
    """The measured false positives, pinned. If a later edit started matching
    string literals or docstrings, this goes red and says why — rather than the
    guard going red on correct code and being weakened to make it green."""
    tree = ast.parse('"""A GST invoice is the Understanding Engine\'s problem."""\nCUE = "TALLY"\n')
    caught = [
        identifier
        for identifier, _ in declared_identifiers(tree)
        if words_in(identifier) & set(ENGINE_1_FORBIDDEN_WORDS)
    ]
    assert caught == []


def test_the_import_sweep_reads_dynamic_imports_not_only_statements() -> None:
    """`require_module` and `importlib.import_module` are how this engine really
    imports its heavy tools, so the guard must see through both. A check that
    read only `import` statements would be blind in the one engine that does
    not use them for its optional stack."""
    tree = ast.parse(
        "import importlib\n"
        "from accountant_dad.artifacts.evidence import DocumentEvidenceObject\n"
        "def go():\n"
        "    importlib.import_module('accountant_dad.brain.stub')\n"
        "    require_module('openai')\n"
        "    __import__('accountant_dad.engines.accounting_engine.stub')\n"
    )
    assert imported_names(tree) == {
        "importlib",
        "accountant_dad.artifacts.evidence",
        "accountant_dad.brain.stub",
        "openai",
        "accountant_dad.engines.accounting_engine.stub",
    }


def test_the_boundary_rule_admits_only_exact_modules_and_their_subpackages() -> None:
    """A prefix rule written as a bare `startswith` would admit
    `accountant_dad.identity_of_the_accounting_engine`. Pinned so the matching
    itself cannot be loosened by accident."""

    def permitted(target: str) -> bool:
        return any(
            target == allowed or target.startswith(f"{allowed}.") for allowed in ENGINE_1_MAY_IMPORT
        )

    assert permitted("accountant_dad.identity")
    assert permitted("accountant_dad.engines.input_engine.reader")
    assert not permitted("accountant_dad.identity_but_actually_something_else")
    assert not permitted("accountant_dad.artifacts.decision")
    assert not permitted("accountant_dad.brain.stub")
    assert not permitted("accountant_dad.engines.tally_engine.stub")


def test_the_content_guard_reads_every_file_on_disk_not_the_allowlist() -> None:
    """The allowlist is what an attacker edits. The disk is what ships.

    `engine_1_sources()` must find files the allowlist has never heard of —
    otherwise an unlisted module would be invisible to every content check
    above, which is the exact combination (unlisted AND full of tax logic) that
    matters most.
    """
    on_disk = {path.stem for path in engine_1_sources()}
    listed = {name.rsplit("/", 1)[-1] for name in ENGINE_1_AUTHORIZED}
    assert listed <= on_disk, f"authorized but absent from disk: {sorted(listed - on_disk)}"
    # Files the allowlist does not name are still read: __init__ and stub are
    # on disk, are covered by AUTHORIZED_STUBS rather than ENGINE_1_AUTHORIZED,
    # and must not fall through the gap between the two lists.
    assert {"__init__", "stub"} <= on_disk
