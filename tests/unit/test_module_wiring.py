"""F-018 — a module that exists, passes its tests, and is wired to nothing.

THE DEFECT. `classification`, `config` and `measurement` are three fully
implemented, mutation-hardened Engine 1 modules with **zero consumers in
`src/`**. Nothing on the real path imports them, so document type is never
determined, the sixteen named confidence parameters are never loaded where it
matters, and no measurement is ever recorded.

WHY NO GATE COULD SEE IT. Every gate that existed asked a question about a
module in isolation. `unit tests` imports the module directly and proves it
works. `coverage` counts the lines those tests executed and is satisfied.
`mutation` mutates the module and finds its tests kill the mutants. All three
go green on a module nothing calls, because **none of them asks whether the
module is reached from anything that runs.** F-012 was the same shape and was
found the same way — by integration, after the fact, three recorded failures
before the single cause was named.

THE TRANSFORM (Law 53). Asking *"does this module do its job in production?"*
needs a running system and a real document. Asking *"is this module reachable
in the import graph from the Application Layer's entry point?"* needs a parser
and answers in milliseconds, is exact, and fails in the same place. The second
question is the one this file asks.

WHAT IT DELIBERATELY DOES NOT DO. It does not wire anything. Reachability is
the DETECTOR; the wiring is a contract change owned elsewhere. A detector that
also fixed what it found would have nothing left to detect.
"""

from __future__ import annotations

import ast

import first_party
import module_wiring
import pytest
from test_package import ENGINE_1_AUTHORIZED

# `services/pipeline.py` is the Application Layer's runner — the only thing in
# `src/` that drives a document through the engines. A module reachable from
# here is a module that runs; a module that is not, is not, whatever its own
# tests say.
APPLICATION_LAYER_ENTRY = "accountant_dad.services.pipeline"

# The exhaustive Engine 1 list, imported from the test that already owns it
# rather than restated here (Law 19). `AUTHORIZED_STUBS` is deliberately NOT
# included: `engines/input_engine/stub` is a declared placeholder that the real
# pipeline replaced, and it is unreachable BY DESIGN. Folding it in would mean
# either a permanently red gate for a reason nobody intends to fix, or an
# exception list — and an exception list is how a gate stops meaning anything.
ENGINE_1_MODULES = frozenset(
    f"accountant_dad.{path.replace('/', '.')}" for path in ENGINE_1_AUTHORIZED
)

# Measured on this tree, not chosen: nine authorised modules, and the three
# F-018 names are the ones with no inbound edge from the entry point.
EXPECTED_ENGINE_1_MODULE_COUNT = 9


def test_the_authorised_set_maps_onto_real_files() -> None:
    """PRECONDITION. A scope built from a typo scans nothing and passes.

    `ENGINE_1_AUTHORIZED` holds slash-separated paths; this file converts them
    to dotted module names. If that conversion ever stops matching the tree,
    every assertion below becomes vacuous, so it is checked before it is used.
    """
    known = set(first_party.module_files())
    assert len(ENGINE_1_MODULES) == EXPECTED_ENGINE_1_MODULE_COUNT
    missing = sorted(ENGINE_1_MODULES - known)
    assert missing == [], f"authorised names that are not modules on disk: {missing}"


def test_the_import_graph_is_not_empty() -> None:
    """HOLLOW-GATE DEFENCE. Reachability over an empty graph flags everything;
    reachability over a graph with no edges flags everything but the entry.
    Both are failure modes that LOOK like a working detector, so the graph's
    shape is asserted before its contents are trusted.
    """
    graph = module_wiring.import_graph()
    assert APPLICATION_LAYER_ENTRY in graph
    assert graph[APPLICATION_LAYER_ENTRY], "the entry point imports nothing; the walk is wrong"
    assert module_wiring.reachable_from(APPLICATION_LAYER_ENTRY) > {APPLICATION_LAYER_ENTRY}


def test_every_authorised_engine_1_module_is_reachable_from_the_application_layer() -> None:
    """THE DETECTOR. A module nothing imports is a module that never runs.

    RED ON THIS TREE, CORRECTLY. `classification`, `config` and `measurement`
    are unreachable — that is F-018 itself, not a defect in this test, and it
    must not be eased (Law 4, §J.4). It goes green when the pipeline imports
    them, which is a contract change owned by another workstream.
    """
    orphans = module_wiring.unreachable(APPLICATION_LAYER_ENTRY, ENGINE_1_MODULES)
    assert orphans == (), (
        "Engine 1 module(s) with no consumer — built, tested, and never run:\n  "
        + "\n  ".join(orphans)
        + f"\n\nNothing reachable from {APPLICATION_LAYER_ENTRY} imports them, so their "
        "behaviour never reaches a document. Wire them into the pipeline, or "
        "record in KNOWN_FAILURES.md why a built module has no consumer."
    )


def test_every_authorised_engine_1_module_is_imported_by_a_test() -> None:
    """A module no test imports has no evidence at all behind it.

    Distinct from reachability and checked separately: a module can be wired
    into the pipeline and still have no tests of its own, and the two failures
    have different fixes.
    """
    untested = module_wiring.not_imported_by_tests(ENGINE_1_MODULES)
    assert untested == (), f"Engine 1 module(s) no test imports: {untested}"


def test_every_authorised_engine_1_module_sits_inside_the_coverage_source_tree() -> None:
    """Coverage measures `source = ["src", "tools/ci"]`. A module outside both
    is invisible to the coverage floor no matter how untested it is.
    """
    outside = module_wiring.outside_coverage_scope(ENGINE_1_MODULES)
    assert outside == (), f"Engine 1 module(s) the coverage gate cannot see: {outside}"


# ═══════════════════════════════════════════════════════════════════════════
# The detector, attacked. Each of these fails if the walk is wrong in a way
# the assertions above would report as success.
# ═══════════════════════════════════════════════════════════════════════════


def test_reachability_follows_a_chain_and_not_just_direct_imports() -> None:
    """`cleaner` is imported by `engines/input_engine/pipeline`, which is
    imported by `services/pipeline` — two hops. A detector that only looked at
    the entry point's own import list would call `cleaner` an orphan and this
    whole file would be noise.
    """
    reachable = module_wiring.reachable_from(APPLICATION_LAYER_ENTRY)
    assert "accountant_dad.engines.input_engine.cleaner" in reachable
    assert "accountant_dad.engines.input_engine.cleaner" not in module_wiring.import_graph().get(
        APPLICATION_LAYER_ENTRY, frozenset()
    ), "precondition: cleaner must be an indirect import, or this proves nothing"


def test_an_unimported_module_is_reported_and_an_imported_one_is_not() -> None:
    """The two directions, on the real tree, in one assertion.

    Without the second half a detector that returns its whole input passes the
    orphan check by accident.

    THE NEGATIVE CONTROL IS `stub`, AND IT USED TO BE `classification`. That was
    correct on the day it was written and it was WIRED TO EXPIRE: `classification`
    was one of the three modules F-018 exists to get consumers for, so the day
    the defect above was fixed this test asserted the opposite of the fix. A
    self-test whose control is a module somebody is actively working to wire is
    a self-test with a countdown on it.

    `engines/input_engine/stub` cannot expire the same way. This file's own
    header already states why: it is *"a declared placeholder that the real
    pipeline replaced, and it is unreachable BY DESIGN"* — which is exactly why
    it is excluded from `ENGINE_1_MODULES` and never reported as a defect. A
    control that is unreachable on purpose is the only kind that stays valid,
    and the assertion is otherwise unchanged: one module in, one module out,
    both directions, no easing.
    """
    orphans = set(
        module_wiring.unreachable(
            APPLICATION_LAYER_ENTRY,
            {
                "accountant_dad.engines.input_engine.cleaner",
                "accountant_dad.engines.input_engine.stub",
            },
        )
    )
    assert orphans == {"accountant_dad.engines.input_engine.stub"}


def test_a_module_reachable_only_from_another_orphan_is_still_an_orphan() -> None:
    """Reachability is from the ENTRY POINT, never "somebody imports it".

    Two orphans importing each other satisfy "has a consumer" and still never
    run. Built as a synthetic graph because the real tree has no such pair —
    which is exactly why the case needs constructing rather than finding.
    """
    graph = {
        "root": frozenset({"live"}),
        "live": frozenset(),
        "dead_a": frozenset({"dead_b"}),
        "dead_b": frozenset({"dead_a"}),
    }
    reached = module_wiring.walk(graph, "root")
    assert reached == {"root", "live"}
    assert module_wiring.unreachable_in(graph, "root", {"dead_a", "dead_b", "live"}) == (
        "dead_a",
        "dead_b",
    )


def test_a_cycle_terminates() -> None:
    """A graph walk with no seen-set hangs the gate instead of failing it."""
    graph = {"a": frozenset({"b"}), "b": frozenset({"a"})}
    assert module_wiring.walk(graph, "a") == {"a", "b"}


def test_an_import_inside_a_function_still_counts_as_an_edge() -> None:
    """A deferred import is still a consumer.

    `reader.py` resolves heavy optional dependencies inside functions. If the
    same style is ever used for a first-party module, refusing to see it would
    report a wired module as an orphan — a false alarm, which is the failure
    that gets a gate weakened.
    """
    tree = ast.parse(
        "def later() -> None:\n"
        "    from accountant_dad.engines.input_engine import config\n"
        "    del config\n"
    )
    edges = module_wiring.edges_from(tree, "accountant_dad.thing", "accountant_dad")
    assert "accountant_dad.engines.input_engine.config" in edges


def test_a_third_party_import_is_never_an_edge() -> None:
    """`import numpy` must not become a node, or the graph stops being about
    this repository and every count in this file is wrong.
    """
    tree = ast.parse("import numpy\nfrom pydantic import BaseModel\n")
    assert module_wiring.edges_from(tree, "accountant_dad.thing", "accountant_dad") == frozenset()


def test_importing_a_symbol_edges_to_the_module_that_defines_it() -> None:
    """`from accountant_dad.confidence import Confidence` imports a CLASS, not
    a module. The edge is still to `accountant_dad.confidence` — without that,
    every module imported only for its symbols reads as an orphan.
    """
    tree = ast.parse("from accountant_dad.confidence import Confidence\n")
    edges = module_wiring.edges_from(tree, "accountant_dad.thing", "accountant_dad")
    assert edges == frozenset({"accountant_dad.confidence"})


def test_importing_a_submodule_by_name_edges_to_the_submodule() -> None:
    """`from accountant_dad.engines.input_engine import config` names a MODULE.
    Edging only to the parent package would leave `config` with no inbound edge
    and this detector would miss the day it finally gets wired.
    """
    tree = ast.parse("from accountant_dad.engines.input_engine import assembly, config\n")
    edges = module_wiring.edges_from(tree, "accountant_dad.thing", "accountant_dad")
    assert edges == frozenset(
        {
            "accountant_dad.engines.input_engine",
            "accountant_dad.engines.input_engine.assembly",
            "accountant_dad.engines.input_engine.config",
        }
    )


def test_an_unknown_entry_point_is_an_error_not_an_empty_answer() -> None:
    """A typo'd entry point makes everything unreachable, which reads as "the
    whole engine is orphaned" — alarming, wrong, and eventually ignored.
    """
    with pytest.raises(module_wiring.UnknownModuleError, match="nope"):
        module_wiring.reachable_from("nope")
