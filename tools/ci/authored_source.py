"""The source of a module AS AUTHORED — never as some tool rewrote it.

WHY THIS EXISTS. A test that parses a module's own source is asking a question
about the REPOSITORY: *"does the code we wrote do X?"* `inspect.getsource`
answers a different question: *"does the code this interpreter is running do
X?"* Those two are the same text only while nothing has rewritten the module,
and mutation testing rewrites every module it mutates.

MEASURED, not assumed. `mutmut run` copies the tree into `mutants/` and injects
a dispatcher into each mutated file. That dispatcher's own body contains

    if mutant_under_test == 'fail':
    elif mutant_under_test == 'stats':

so `tests/unit/test_input_engine_assembly_redteam.py::
test_assembly_compares_only_against_none` — which asserts assembly compares
against nothing but `None` — read mutmut's comparisons as if this repository
had written them:

    AssertionError: assembly compares against something other than None:
      [(136, ["Constant(value='fail')"]), (139, ["Constant(value='stats')"])]
    failed to collect stats. runner returned 1

mutmut collects those stats by running the whole suite once BEFORE the first
mutant. One red test there aborts the run, so the entire gate died in six
minutes reporting `4075 not checked` and scored nothing. The test was correct
about the authored file and wrong about where to find it.

THE OTHER DIRECTION IS WORSE. mutmut also renames every function — `run`
becomes `x_run__mutmut_orig` and the public name becomes the dispatcher — so
`inspect.getsource(pipeline.run)` returns the DISPATCHER, not the body. A test
asserting "`run` never calls `min()`" then passes because it is reading eight
lines of mutmut boilerplate that indeed calls no `min()`. That is a false
green, and unlike the red one nothing reports it.

WHAT THIS DOES. `mutants/` is a copy, never a move: the authored file is still
on disk at the same path with that one directory component removed. So the fix
is not to make the assertions tolerate instrumentation — it is to stop reading
the instrumented text at all. Removal is only performed when a real file exists
at the resulting path, so a repository that genuinely has a directory named
`mutants` is unaffected.

Ten modules — the `[tool.mutmut] do_not_mutate` list — are copied pristine and
carry no dispatcher, which is why their source-parsing tests never noticed.
That is luck, not design: moving a module out of that list would have broken
them. Routing every reader through here removes the dependency entirely.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path
from types import ModuleType

# The directory mutmut copies the tree into. Not configurable in mutmut 3.3.1:
# `__main__.py` writes to a literal `mutants/` beside the project root.
MUTATION_COPY_DIRECTORY = "mutants"


class AuthoredSourceUnavailableError(Exception):
    """Raised when the file a module claims to come from is not on disk.

    Never silently falls back to the instrumented text: a test that cannot see
    the authored source has no basis for asserting anything about it, and must
    fail loudly rather than assert against a rewrite (Law 11).
    """


def authored_path(module: ModuleType) -> Path:
    """The path of `module`'s file in the authored tree.

    Returns the file unchanged when nothing has copied it. When the module was
    imported out of a mutation copy, returns the corresponding authored file —
    but only if that file actually exists, so the redirect can never invent a
    path.
    """
    running = Path(inspect.getfile(module)).resolve()
    for index, part in enumerate(running.parts):
        if part != MUTATION_COPY_DIRECTORY:
            continue
        authored = Path(*running.parts[:index], *running.parts[index + 1 :])
        if authored.is_file():
            return authored
    if not running.is_file():
        raise AuthoredSourceUnavailableError(
            f"{module.__name__} claims to come from {running}, which is not a file. "
            "Nothing can be asserted about source that cannot be read."
        )
    return running


def running_path(module: ModuleType) -> Path:
    """The path the interpreter actually loaded `module` from, rewrites and all.

    The deliberate opposite of `authored_path`, and it exists so that choosing
    the instrumented copy is a decision somebody wrote down rather than the
    accident of reaching for `__file__`. Two callers genuinely need it:

    `runpy.run_path` on a CLI entry point. Executing the AUTHORED file under
    mutation would run un-mutated code, so every mutant in those modules would
    survive undetectably and the score would be wrong in the direction that
    looks fine. Whatever is being executed must be what is being scored.

    A test whose subject IS the mutation copy — `test_mutation_measures_the_
    real_tree` exists to prove mutmut scores the instrumented tree, and cannot
    prove it by reading the authored one.

    Anything that merely READS source to assert a property of this repository
    wants `authored_path` instead.
    """
    return Path(inspect.getfile(module)).resolve()


def authored_repo_root() -> Path:
    """The repository root of the AUTHORED tree, never a mutation copy.

    The third spelling of this defect, and the one that cost a whole mutation
    run at `4fc7187`. A test that writes

        REPO = pathlib.Path(__file__).resolve().parents[2]
        PACKAGE = REPO / "src" / "accountant_dad"

    is reading its OWN location — and under mutation the test file itself lives
    in `mutants/`, so `PACKAGE` resolves to the instrumented copies. Every path
    derived from `__file__` inherits whichever tree the test was loaded from.

    It went unnoticed for as long as it did because the instrumented and
    authored trees agreed on everything that test asked about. mutmut 3.7.0
    ended that: its dispatcher imports `mutmut` at module scope, so
    `test_declared_dependencies` — which derives the needed distribution set by
    walking the package's AST — correctly reported that thirty-three modules
    "need one of ['mutmut']", failed the stats phase, and left all 4097 mutants
    unscored.

    Bare `__file__` is not banned: a test locating its own fixtures is right to
    use it. What must not happen is deriving the SOURCE TREE from it.
    """
    here = Path(__file__).resolve()
    for index, part in enumerate(here.parts):
        if part != MUTATION_COPY_DIRECTORY:
            continue
        candidate = Path(*here.parts[:index])
        if (candidate / "pyproject.toml").is_file():
            return candidate
    # `tools/ci/authored_source.py` -> repository root
    return here.parents[2]


def authored_source(module: ModuleType) -> str:
    """The full text of `module` as authored."""
    return authored_path(module).read_text(encoding="utf-8")


def authored_tree(module: ModuleType) -> ast.Module:
    """`module`'s authored source, parsed.

    Every caller that walks a parse tree wants this rather than
    `ast.parse(inspect.getsource(...))`, and having it here means the parse
    happens against the authored text by construction.
    """
    return ast.parse(authored_source(module))


def authored_function_source(module: ModuleType, name: str) -> str:
    """The text of one authored function or method, found by name.

    Takes the name rather than the function object on purpose. Under mutation
    the object bound to `module.name` is a generated dispatcher whose source is
    boilerplate; the authored body is only reachable through the file.

    Nested definitions are excluded — `ast.walk` would otherwise return an
    inner helper that happens to share a name with the function asked for.
    """
    source = authored_source(module)
    for node in ast.parse(source).body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name == name:
            segment = ast.get_source_segment(source, node)
            if segment is None:
                raise AuthoredSourceUnavailableError(
                    f"{module.__name__}.{name} has no recoverable source segment."
                )
            return segment
    raise AuthoredSourceUnavailableError(
        f"{module.__name__} defines no top-level function named {name!r}."
    )
