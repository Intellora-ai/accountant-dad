"""Does every call site still bind to its callee's parameters? (F-025)

WHAT BROKE. `pipeline.run` gained a required keyword-only `recorded_at`. One
side of the call was updated; two recovered test files, written against the
older contract, were not:

    TypeError: run() missing 1 required keyword-only argument: 'recorded_at'

Thirty-nine of forty failures were that one line. The damage was not the red —
it was that 1712 lines of red-team and ablation tests could not execute, and a
test that cannot execute cannot fail. They looked like coverage and were not.

THE TRANSFORM (Law 53). *"Does every test still run?"* requires running them,
takes 245 seconds, and presupposes the suite collects at all — which under
F-024 it did not. *"Does every call's argument list bind to its callee's
parameters?"* is arithmetic over two parse trees: build the callee's signature
from its authored `def`, bind the call's arguments to it, and report what
`Signature.bind` rejects. Under a second, every offender at once, and it works
on a file that cannot be imported.

MUTATION-SAFE BY CONSTRUCTION. Signatures come from the authored `def`, never
from `inspect.signature` of the live object. Under `mutmut run` the live
`pipeline.run` is a generated dispatcher taking `(*args, **kwargs)`, which
binds every call — so an `inspect`-based version of this check would report
green on a tree full of stale call sites at precisely the moment the tree was
most rewritten. The binding ALGORITHM is still `inspect`'s, because
reimplementing Python's argument-matching rules would be a second source of
truth for something the standard library already owns exactly (Law 15).

CONSERVATIVE WHERE IT CANNOT BE EXACT. A call it cannot resolve with certainty
is not checked, and `unchecked` reports why rather than letting silence read as
verification. That direction is deliberate: a missed check is a gap, but a
WRONG check is a false alarm on correct code, and a gate that cries wolf is a
gate somebody eventually weakens (§J.4).

SCOPE. Calls to top-level FUNCTIONS of first-party modules. Classes are out of
scope on purpose — a dataclass's or a Pydantic model's `__init__` is generated
rather than authored, so there is no `def` to read, and guessing one from the
class body would produce exactly the false alarms this module refuses to make.
`unresolved_symbols` owns whether a name exists at all; this module owns only
whether a call matches the function behind it.
"""

from __future__ import annotations

import ast
import inspect
from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from typing import NamedTuple

import first_party

type FunctionNode = ast.FunctionDef | ast.AsyncFunctionDef
type FunctionTable = Mapping[str, Mapping[str, FunctionNode]]

#: A floor, not the count. A resolver that silently stops resolving checks
#: nothing and returns `()`, which is indistinguishable from success. Measured
#: on the tree this was written against: 882 checked call sites under `tests/`,
#: covering 91 distinct callees, of which 28 are `pipeline.run` — the function
#: F-025 was about.
FEWEST_CALLS_THAT_CAN_BE_REAL = 300

#: Stands in for every argument value. Only arity and names are being checked,
#: so the value never matters — but it must be a real object, because
#: `Signature.bind` inspects what it is given.
_VALUE = object()


class Drift(NamedTuple):
    """One call site whose arguments no longer match its callee."""

    file: str
    line: int
    module: str
    function: str
    reason: str

    def __str__(self) -> str:
        return f"{self.file}:{self.line} {self.module}.{self.function}(...) — {self.reason}"


class Unchecked(NamedTuple):
    """One call site this module declines to judge, and why."""

    file: str
    line: int
    module: str
    function: str
    reason: str

    def __str__(self) -> str:
        return f"{self.file}:{self.line} {self.module}.{self.function}(...) — {self.reason}"


class CallSite(NamedTuple):
    """One call site that WAS checked."""

    file: str
    line: int
    module: str
    function: str


def signature_of(node: FunctionNode) -> inspect.Signature:
    """The signature of an authored `def`, every parameter kind preserved.

    Positional-only and keyword-only are not decoration: `run`'s parameters are
    keyword-only, so a binder that flattened the `*` would accept
    `run(intake, identity, settings, recorded_at)` — which raises at runtime.
    That is a false green on the exact function F-025 was about.
    """
    arguments = node.args
    parameters: list[inspect.Parameter] = []
    kind = inspect.Parameter

    positional = list(arguments.posonlyargs) + list(arguments.args)
    first_defaulted = len(positional) - len(arguments.defaults)
    for index, argument in enumerate(positional):
        parameters.append(
            inspect.Parameter(
                argument.arg,
                kind.POSITIONAL_ONLY
                if index < len(arguments.posonlyargs)
                else kind.POSITIONAL_OR_KEYWORD,
                default=kind.empty if index < first_defaulted else _VALUE,
            )
        )

    if arguments.vararg is not None:
        parameters.append(inspect.Parameter(arguments.vararg.arg, kind.VAR_POSITIONAL))

    for argument, default in zip(arguments.kwonlyargs, arguments.kw_defaults, strict=True):
        parameters.append(
            inspect.Parameter(
                argument.arg,
                kind.KEYWORD_ONLY,
                default=kind.empty if default is None else _VALUE,
            )
        )

    if arguments.kwarg is not None:
        parameters.append(inspect.Parameter(arguments.kwarg.arg, kind.VAR_KEYWORD))

    return inspect.Signature(parameters)


def rebound_names(tree: ast.Module) -> frozenset[str]:
    """Every name the file binds anywhere OTHER than by importing it.

    A file that assigns to the name it imported, or shadows it with a
    parameter, is no longer talking about the module. Checking calls through
    such a name would compare a call against an unrelated function — the false
    alarm this module exists to avoid.
    """
    rebound: set[str] = set()
    for node in ast.walk(tree):
        rebound |= _binds(node)
    return frozenset(rebound)


def _binds(node: ast.AST) -> set[str]:
    if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
        return {node.id}
    if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
        arguments = node.args
        every = [
            *arguments.posonlyargs,
            *arguments.args,
            *arguments.kwonlyargs,
            *([arguments.vararg] if arguments.vararg else []),
            *([arguments.kwarg] if arguments.kwarg else []),
        ]
        return {node.name} | {argument.arg for argument in every}
    if isinstance(node, ast.Lambda):
        return {argument.arg for argument in [*node.args.args, *node.args.kwonlyargs]}
    if isinstance(node, ast.ClassDef):
        return {node.name}
    if isinstance(node, ast.ExceptHandler) and node.name is not None:
        return {node.name}
    return set()


def local_bindings(
    tree: ast.Module, package: str, known: AbstractSet[str]
) -> tuple[dict[str, str], dict[str, tuple[str, str]]]:
    """What each local name refers to: a first-party module, or a function in one.

    Returns `(modules, functions)`. A name that is rebound anywhere in the file
    appears in neither.
    """
    modules: dict[str, str] = {}
    functions: dict[str, tuple[str, str]] = {}

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in known:
                    modules[alias.asname or alias.name.split(".")[0]] = alias.name
        elif isinstance(node, ast.ImportFrom):
            base = first_party.absolute_module(node, package)
            if base is None:
                continue
            for alias in node.names:
                local = alias.asname or alias.name
                if f"{base}.{alias.name}" in known:
                    modules[local] = f"{base}.{alias.name}"
                elif base in known:
                    functions[local] = (base, alias.name)

    rebound = rebound_names(tree)
    return (
        {name: target for name, target in modules.items() if name not in rebound},
        {name: target for name, target in functions.items() if name not in rebound},
    )


def _callee(
    call: ast.Call, modules: Mapping[str, str], functions: Mapping[str, tuple[str, str]]
) -> tuple[str, str] | None:
    """Which first-party function a call names, if that is knowable."""
    func = call.func
    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
        module = modules.get(func.value.id)
        return None if module is None else (module, func.attr)
    if isinstance(func, ast.Name):
        return functions.get(func.id)
    return None


def _is_exact(call: ast.Call) -> bool:
    """Whether the call's arity is knowable without executing it."""
    if any(isinstance(argument, ast.Starred) for argument in call.args):
        return False
    return all(keyword.arg is not None for keyword in call.keywords)


def _bind(node: FunctionNode, call: ast.Call) -> str | None:
    """The binding error for this call, or `None` when it binds."""
    try:
        signature_of(node).bind(
            *[_VALUE for _ in call.args],
            **{str(keyword.arg): _VALUE for keyword in call.keywords},
        )
    except TypeError as error:
        return str(error)
    return None


def drift(
    tree: ast.Module, filename: str, table: FunctionTable, known: AbstractSet[str]
) -> tuple[Drift, ...]:
    """Every call in `tree` that no longer binds to its first-party callee."""
    modules, functions = local_bindings(tree, first_party.PACKAGE, known)
    findings: list[Drift] = []

    for call in [n for n in ast.walk(tree) if isinstance(n, ast.Call)]:
        target = _callee(call, modules, functions)
        if target is None or not _is_exact(call):
            continue
        module, name = target
        node = table.get(module, {}).get(name)
        if node is None:
            continue
        reason = _bind(node, call)
        if reason is not None:
            findings.append(Drift(filename, call.lineno, module, name, reason))

    return tuple(findings)


def unchecked(
    tree: ast.Module, filename: str, table: FunctionTable, known: AbstractSet[str]
) -> tuple[Unchecked, ...]:
    """Every first-party call this module declines to judge, and why.

    Exists so that "not reported" and "verified" stay distinguishable. A
    validator whose silence covers both is one that quietly stops checking.
    """
    modules, functions = local_bindings(tree, first_party.PACKAGE, known)
    skipped: list[Unchecked] = []

    for call in [n for n in ast.walk(tree) if isinstance(n, ast.Call)]:
        target = _callee(call, modules, functions)
        if target is None:
            continue
        module, name = target
        if module in table and name in table[module] and not _is_exact(call):
            skipped.append(
                Unchecked(
                    filename,
                    call.lineno,
                    module,
                    name,
                    "unpacked argument — arity is not knowable without executing it",
                )
            )
    return tuple(skipped)


def repository_functions() -> FunctionTable:
    """Every top-level function of every first-party module, as authored."""
    return {
        dotted: first_party.top_level_functions(first_party.parse(path))
        for dotted, path in first_party.module_files().items()
    }


def _test_files() -> list[tuple[str, ast.Module]]:
    root = first_party.repo_root()
    tests = root / "tests"
    return [
        (str(path.relative_to(root)), first_party.parse(path))
        for path in sorted(tests.rglob("*.py"))
    ]


def drift_in_tests() -> tuple[Drift, ...]:
    """Every stale call site under `tests/`."""
    table = repository_functions()
    known = frozenset(first_party.module_files())
    findings: list[Drift] = []
    for filename, tree in _test_files():
        findings.extend(drift(tree, filename, table, known))
    return tuple(findings)


def checked_call_sites() -> tuple[CallSite, ...]:
    """Every call site under `tests/` that was actually bound and judged."""
    table = repository_functions()
    known = frozenset(first_party.module_files())
    checked: list[CallSite] = []

    for filename, tree in _test_files():
        modules, functions = local_bindings(tree, first_party.PACKAGE, known)
        for call in [n for n in ast.walk(tree) if isinstance(n, ast.Call)]:
            target = _callee(call, modules, functions)
            if target is None or not _is_exact(call):
                continue
            module, name = target
            if name in table.get(module, {}):
                checked.append(CallSite(filename, call.lineno, module, name))
    return tuple(checked)
