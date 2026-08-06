"""F-025 — production grew a parameter and the call sites were never told.

THE DEFECT. `pipeline.run` gained a required keyword-only `recorded_at`.
`b3c1b51` updated the Application Layer's side of that call. Two test files
recovered at `211c6b0` — written against the OLD signature — were not:

    TypeError: run() missing 1 required keyword-only argument: 'recorded_at'

Thirty-nine of the forty failures at that commit were that one line. The cost
was not the red: it was that 1081 lines of pipeline red-team tests and 631
lines of ablation tests — the tests guarding F-012's `reader → parser` pipe and
Engine 1's identity-leak boundary — **were not running at all.** A test that
cannot execute cannot fail, so it proves nothing while looking like coverage.

WHY NO GATE CAUGHT IT. Nothing compares a call against its callee. `mypy` does,
but only through a resolved import, and `pipeline` is reached in those files
through fixtures and helpers it cannot follow. `unit tests` catches it by
RUNNING it — which is exactly what was not happening, because the same suite
run that would have reported it was the one being blocked by F-024.

THE CLASS. Recovered work carries the contract it was written against.
Recovery-not-restart (D-006) is still correct; the missing half is that an
inherited file is untrusted until it has been checked against the CURRENT
signature, not merely committed.

THE TRANSFORM (Law 53). *"Does every test still run?"* needs the whole suite,
takes 245 seconds, and needs the suite to be collectable in the first place.
*"Does every call site's argument list still bind to its callee's
parameters?"* is arithmetic over two parse trees. It answers in under a second,
names every stale call site at once, and — decisively — reports them even when
the module they live in cannot be imported.

MUTATION-SAFE BY CONSTRUCTION. Signatures are built from the AUTHORED `def`,
never from `inspect.signature` of the live object. Under `mutmut run` the live
`pipeline.run` is a generated dispatcher taking `(*args, **kwargs)`, which
binds ANY call — so an `inspect`-based version of this validator would report
green on every stale call site in the tree at exactly the moment it mattered.
"""

from __future__ import annotations

import ast
import inspect

import first_party
import pytest
import signature_drift

# `run` as it is authored now, and the call as the two unupdated files wrote
# it. Reproduces F-025 exactly: three arguments that were correct, and the
# fourth that arrived after those files were written.
RUN_AS_AUTHORED_NOW = """\
def run(intake, *, identity, settings, recorded_at):
    return None
"""

CALL_AS_THE_STALE_FILES_WROTE_IT = """\
from accountant_dad.engines.input_engine import pipeline

def test_something():
    evidence = pipeline.run(intake, identity=an_identity(), settings=strict)
"""

CALL_AS_THE_UPDATED_FILE_WROTE_IT = """\
from accountant_dad.engines.input_engine import pipeline

def test_something():
    evidence = pipeline.run(
        intake, identity=an_identity(), settings=strict, recorded_at=RECORDED_AT
    )
"""

PIPELINE = "accountant_dad.engines.input_engine.pipeline"

#: The line `pipeline.run(...)` sits on in `CALL_AS_THE_STALE_FILES_WROTE_IT` —
#: inside the test body, not the import above it and not the `def` around it.
LINE_OF_THE_STALE_CALL = 4

#: `f(*args)` and `f(**kwargs)`: both unpacking forms must be declined, not one.
BOTH_UNPACKING_FORMS = 2


def _functions(**modules: str) -> dict[str, dict[str, ast.FunctionDef | ast.AsyncFunctionDef]]:
    """A function table built from source text, the shape the real scan builds."""
    return {
        name.replace("__", "."): first_party.top_level_functions(ast.parse(text))
        for name, text in modules.items()
    }


def _table() -> dict[str, dict[str, ast.FunctionDef | ast.AsyncFunctionDef]]:
    return {PIPELINE: first_party.top_level_functions(ast.parse(RUN_AS_AUTHORED_NOW))}


# ═══════════════════════════════════════════════════════════════════════════
# The regression. This is the call that produced 39 identical failures.
# ═══════════════════════════════════════════════════════════════════════════


def test_the_thirty_nine_failures_do_not_recur() -> None:
    """A call missing a required keyword-only argument is named, with its line."""
    findings = signature_drift.drift(
        ast.parse(CALL_AS_THE_STALE_FILES_WROTE_IT),
        "test_input_engine_pipeline_redteam.py",
        _table(),
        frozenset({PIPELINE}),
    )
    assert len(findings) == 1, f"expected exactly the stale call; got {findings}"
    assert findings[0].function == "run"
    assert findings[0].module == PIPELINE
    assert "recorded_at" in findings[0].reason
    # The call, not the import and not the enclosing `def`. A validator that
    # reported the file without the line leaves 39 call sites to find by hand.
    assert findings[0].line == LINE_OF_THE_STALE_CALL
    assert f"test_input_engine_pipeline_redteam.py:{LINE_OF_THE_STALE_CALL}" in str(findings[0])


def test_the_updated_call_is_not_reported() -> None:
    """FALSE-POSITIVE GUARD. `test_input_engine_pipeline.py` passed
    `recorded_at` and was correct. Flagging it too would make the gate noise.
    """
    findings = signature_drift.drift(
        ast.parse(CALL_AS_THE_UPDATED_FILE_WROTE_IT),
        "test_input_engine_pipeline.py",
        _table(),
        frozenset({PIPELINE}),
    )
    assert findings == ()


# ═══════════════════════════════════════════════════════════════════════════
# The real tree.
# ═══════════════════════════════════════════════════════════════════════════


def test_every_call_site_in_the_tests_binds_to_its_callee() -> None:
    """THE DETECTOR, over every file under `tests/`.

    Goes red naming file, line, callee and the exact binding error the moment a
    production signature moves without its call sites.
    """
    findings = signature_drift.drift_in_tests()
    assert findings == (), "call site(s) that no longer match their callee:\n  " + "\n  ".join(
        str(finding) for finding in findings
    )


def test_the_scan_actually_resolves_real_call_sites() -> None:
    """HOLLOW-GATE DEFENCE. A validator that resolves nothing checks nothing
    and returns `()`. Pin that it really binds a known, real call.

    `pipeline.run` is the exact function F-025 was about, so if resolution ever
    silently stops working, the one call site that must never go unchecked is
    the one this asserts is checked.
    """
    checked = signature_drift.checked_call_sites()
    assert len(checked) >= signature_drift.FEWEST_CALLS_THAT_CAN_BE_REAL
    assert (PIPELINE, "run") in {(site.module, site.function) for site in checked}


# ═══════════════════════════════════════════════════════════════════════════
# The binder, attacked. Every one of these is a way to be wrong that would
# read as success.
# ═══════════════════════════════════════════════════════════════════════════


def test_too_many_positional_arguments_is_drift() -> None:
    """The opposite direction from a missing argument — a parameter REMOVED."""
    findings = signature_drift.drift(
        ast.parse("from accountant_dad.m import f\ng = f(1, 2, 3)\n"),
        "t.py",
        _functions(accountant_dad__m="def f(a, b):\n    return None\n"),
        frozenset({"accountant_dad.m"}),
    )
    assert len(findings) == 1
    assert "too many positional" in findings[0].reason


def test_a_renamed_required_parameter_is_drift() -> None:
    """A parameter RENAMED reaches the call site as an unknown keyword.

    Python reports the MISSING name first, not the surplus one, so the message
    is pinned to what `Signature.bind` actually says rather than to what reads
    well — a reason string nobody verified is a reason string that drifts.
    """
    findings = signature_drift.drift(
        ast.parse("from accountant_dad.m import f\ng = f(when=1)\n"),
        "t.py",
        _functions(accountant_dad__m="def f(recorded_at):\n    return None\n"),
        frozenset({"accountant_dad.m"}),
    )
    assert len(findings) == 1
    assert findings[0].reason == "missing a required argument: 'recorded_at'"


def test_an_unexpected_keyword_argument_is_drift() -> None:
    """A surplus keyword, with nothing missing to mask it."""
    findings = signature_drift.drift(
        ast.parse("from accountant_dad.m import f\ng = f(when=1)\n"),
        "t.py",
        _functions(accountant_dad__m="def f(recorded_at=None):\n    return None\n"),
        frozenset({"accountant_dad.m"}),
    )
    assert len(findings) == 1
    assert findings[0].reason == "got an unexpected keyword argument 'when'"


def test_a_defaulted_parameter_may_be_omitted() -> None:
    """A parameter with a default is not required. Treating every parameter as
    required would flag most correct calls in the repository.
    """
    findings = signature_drift.drift(
        ast.parse("from accountant_dad.m import f\ng = f(1)\n"),
        "t.py",
        _functions(accountant_dad__m="def f(a, b=2, *, c=3):\n    return None\n"),
        frozenset({"accountant_dad.m"}),
    )
    assert findings == ()


def test_var_positional_and_var_keyword_accept_anything() -> None:
    """`def f(*args, **kwargs)` binds every call. Reporting one would be a
    false alarm, and false alarms are what get a gate switched off.
    """
    findings = signature_drift.drift(
        ast.parse("from accountant_dad.m import f\ng = f(1, 2, x=3)\n"),
        "t.py",
        _functions(accountant_dad__m="def f(*args, **kwargs):\n    return None\n"),
        frozenset({"accountant_dad.m"}),
    )
    assert findings == ()


def test_a_keyword_only_parameter_cannot_be_passed_positionally() -> None:
    """`run`'s parameters are keyword-only. A binder that ignored the `*`
    would accept `run(intake, identity, settings, recorded_at)`, which raises
    at runtime — a false green on the exact function F-025 was about.
    """
    findings = signature_drift.drift(
        ast.parse("from accountant_dad.m import f\ng = f(1, 2)\n"),
        "t.py",
        _functions(accountant_dad__m="def f(a, *, b):\n    return None\n"),
        frozenset({"accountant_dad.m"}),
    )
    assert len(findings) == 1


def test_a_positional_only_parameter_cannot_be_passed_by_keyword() -> None:
    """The `/` marker is real and binds differently."""
    findings = signature_drift.drift(
        ast.parse("from accountant_dad.m import f\ng = f(a=1)\n"),
        "t.py",
        _functions(accountant_dad__m="def f(a, /):\n    return None\n"),
        frozenset({"accountant_dad.m"}),
    )
    assert len(findings) == 1


def test_a_starred_call_argument_is_skipped_rather_than_guessed() -> None:
    """`f(*args)` hides its arity. Guessing it would produce a false alarm on
    correct code, so the call is not checked — and `unchecked_reasons` says so
    out loud rather than letting it look verified.
    """
    tree = ast.parse("from accountant_dad.m import f\ng = f(*args)\nh = f(**kwargs)\n")
    table = _functions(accountant_dad__m="def f(a, b):\n    return None\n")
    known = frozenset({"accountant_dad.m"})
    assert signature_drift.drift(tree, "t.py", table, known) == ()
    skipped = signature_drift.unchecked(tree, "t.py", table, known)
    assert len(skipped) == BOTH_UNPACKING_FORMS
    assert {site.line for site in skipped} == {2, 3}


def test_a_rebound_alias_is_never_resolved() -> None:
    """If a file assigns to the name it imported, the name no longer refers to
    the module and every call through it would be checked against the wrong
    function. Conservative by design: a missed check is a gap, a wrong check is
    a false alarm that gets the gate deleted.
    """
    tree = ast.parse(
        "from accountant_dad.m import f\nf = lambda *a, **k: None\ng = f(1, 2, 3, 4, 5)\n"
    )
    table = _functions(accountant_dad__m="def f(a):\n    return None\n")
    assert signature_drift.drift(tree, "t.py", table, frozenset({"accountant_dad.m"})) == ()


def test_a_shadowing_function_parameter_rebinds_too() -> None:
    """`def helper(pipeline):` makes `pipeline` a parameter, not the module."""
    tree = ast.parse("from accountant_dad.m import f\ndef helper(f):\n    return f(1, 2, 3)\n")
    table = _functions(accountant_dad__m="def f(a):\n    return None\n")
    assert signature_drift.drift(tree, "t.py", table, frozenset({"accountant_dad.m"})) == ()


def test_a_call_to_a_third_party_function_is_never_checked() -> None:
    """`json.dumps(...)` is not this repository's contract."""
    tree = ast.parse("import json\ng = json.dumps(1, 2, 3, 4)\n")
    assert signature_drift.drift(tree, "t.py", {}, frozenset()) == ()


def test_a_method_call_on_an_instance_is_not_mistaken_for_a_module_function() -> None:
    """`settings.replace(...)` is an attribute of a VALUE. Resolving it against
    a module of the same name would compare a call to an unrelated function.
    """
    tree = ast.parse("settings = build()\ng = settings.replace(1, 2, 3)\n")
    table = _functions(accountant_dad__settings="def replace(a):\n    return None\n")
    assert signature_drift.drift(tree, "t.py", table, frozenset({"accountant_dad.settings"})) == ()


def test_a_class_is_not_treated_as_a_function() -> None:
    """Only top-level `def`s are checked. A dataclass's `__init__` is generated
    from its fields, and reading the `class` body as a signature would compare
    every construction against nothing.
    """
    tree = ast.parse("from accountant_dad.m import Thing\ng = Thing(1, 2, 3)\n")
    table = _functions(accountant_dad__m="class Thing:\n    pass\n")
    assert signature_drift.drift(tree, "t.py", table, frozenset({"accountant_dad.m"})) == ()


def test_an_unknown_function_on_a_known_module_is_not_a_binding_error() -> None:
    """`pipeline.PipelineSettings(...)` is a class on a real module. It is out
    of scope here, and `unresolved_symbols` owns whether the name exists — two
    validators, one question each.
    """
    tree = ast.parse("from accountant_dad import m\ng = m.absent(1, 2, 3)\n")
    table = _functions(accountant_dad__m="def present(a):\n    return None\n")
    assert signature_drift.drift(tree, "t.py", table, frozenset({"accountant_dad.m"})) == ()


def test_the_signature_builder_reproduces_every_parameter_kind() -> None:
    """Built from the AST, so name, kind AND requiredness are each asserted.

    Compared structurally rather than by `str(signature)`: the repr embeds the
    sentinel's memory address, so a repr comparison would be testing `object`'s
    `__repr__` and would pass whatever the kinds were.
    """
    node = first_party.top_level_functions(
        ast.parse("def f(p, /, a, b=1, *rest, c, d=2, **extra):\n    return None\n")
    )["f"]
    kind = inspect.Parameter
    actual = [
        (parameter.name, parameter.kind, parameter.default is inspect.Parameter.empty)
        for parameter in signature_drift.signature_of(node).parameters.values()
    ]
    assert actual == [
        ("p", kind.POSITIONAL_ONLY, True),
        ("a", kind.POSITIONAL_OR_KEYWORD, True),
        ("b", kind.POSITIONAL_OR_KEYWORD, False),
        ("rest", kind.VAR_POSITIONAL, True),
        ("c", kind.KEYWORD_ONLY, True),
        ("d", kind.KEYWORD_ONLY, False),
        ("extra", kind.VAR_KEYWORD, True),
    ]


def test_an_async_function_is_checked_like_any_other() -> None:
    """`async def` binds identically; skipping it would be a silent hole."""
    findings = signature_drift.drift(
        ast.parse("from accountant_dad.m import f\ng = f()\n"),
        "t.py",
        _functions(accountant_dad__m="async def f(a):\n    return None\n"),
        frozenset({"accountant_dad.m"}),
    )
    assert len(findings) == 1


def test_an_unparseable_test_file_fails_loudly() -> None:
    """A test file that cannot be parsed cannot be collected either."""
    with pytest.raises(SyntaxError):
        first_party.parse_text("def broken(:\n", "broken.py")
