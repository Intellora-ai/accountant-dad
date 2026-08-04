"""The mutation gate must measure the code the tests actually import.

THE BUG THIS EXISTS TO PREVENT, because it cost a whole day and produced a
number that looked like a measurement and was not one.

The `mutation` job in `testing.yml` set `PYTHONPATH: tools/ci:src`. Python
resolves PYTHONPATH to ABSOLUTE paths at interpreter STARTUP, while the working
directory is still the repository root, so `src` became
`/…/accountant dad/src` — the ORIGINAL tree. mutmut then chdirs into `mutants/`
and runs the suite through `pytest.main()`, IN-PROCESS, in that same
interpreter. Those absolute entries were still on `sys.path` and still won, so
every test imported pristine code and every mutant survived by construction.

CI reported `0 killed / 351 survived`, a 0.0% score. Nothing was broken. The
tests were fine. The gate was measuring a tree nobody was testing.

`chdir` cannot retract a `sys.path` entry that is already absolute. That is the
whole mechanism, and it is invisible in the workflow file — the line looks
correct, and it is correct for every other job in the repository.

WHAT MAKES IT WORK INSTEAD

`[tool.pytest.ini_options] pythonpath` in `pyproject.toml`. pytest resolves
those entries relative to ROOTDIR, and mutmut passes `--rootdir=.` from inside
`mutants/`, so they resolve to the instrumented copies. pytest PREPENDS them,
which is also why this survives an editable install: a `.pth` file appends its
path, and a prepend beats an append.

These assertions are cheap and deterministic on purpose. They do not run a
mutation pass; they check that the two conditions which make one meaningful are
still true. A test that needed a real mutation run would be too slow to keep,
and a guard nobody runs guards nothing.
"""

from __future__ import annotations

import pathlib
import tomllib

import yaml

REPO = pathlib.Path(__file__).resolve().parents[2]
TESTING_WORKFLOW = REPO / ".github" / "workflows" / "testing.yml"
PYPROJECT = REPO / "pyproject.toml"

#: The job whose steps must never put the original tree on `sys.path`.
MUTATION_JOB = "mutation"

#: `tools/ci` is flat on the path and `src` holds the package. Both must be
#: resolvable relative to whichever tree pytest is rooted in — the real one
#: normally, the instrumented copy under mutation.
REQUIRED_PYTHONPATH = ["tools/ci", "src"]


def mutation_job() -> dict[str, object]:
    document = yaml.safe_load(TESTING_WORKFLOW.read_text(encoding="utf-8"))
    jobs = document["jobs"]
    assert MUTATION_JOB in jobs, (
        f"no {MUTATION_JOB!r} job in testing.yml. It was renamed or removed; "
        "this guard is now pointing at nothing."
    )
    return dict(jobs[MUTATION_JOB])


def pyproject() -> dict[str, object]:
    with PYPROJECT.open("rb") as handle:
        return tomllib.load(handle)


def test_the_mutation_job_never_puts_the_original_tree_on_the_path() -> None:
    """The exact line that made the gate measure nothing. It may not return.

    Checked at every level a value can hide: the job's own `env`, each step's
    `env`, and the shell body of each `run` — because `export PYTHONPATH=...`
    inside a script does the identical damage and would slip past a check that
    only read the `env` mappings.
    """
    job = mutation_job()

    job_env = job.get("env") or {}
    assert isinstance(job_env, dict)
    assert "PYTHONPATH" not in job_env, (
        "the mutation job sets PYTHONPATH at job level. Python absolutises it "
        "at interpreter startup against the repository root, so mutmut's later "
        "chdir into mutants/ cannot retract it and every mutant survives."
    )

    steps = job.get("steps") or []
    assert isinstance(steps, list)
    for index, step in enumerate(steps):
        assert isinstance(step, dict)
        label = step.get("name", f"<step {index}>")

        step_env = step.get("env") or {}
        assert isinstance(step_env, dict)
        assert "PYTHONPATH" not in step_env, (
            f"step {label!r} sets PYTHONPATH. That is the defect this file "
            "exists to prevent: the gate then scores the original tree, which "
            "no test imports, and reports 0 killed with everything surviving."
        )

        body = step.get("run") or ""
        assert isinstance(body, str)
        assert "PYTHONPATH" not in body, (
            f"step {label!r} mentions PYTHONPATH in its shell body. Exporting "
            "it there does exactly the same damage as setting it in `env`."
        )


def test_pytest_carries_the_import_path_so_it_follows_the_rootdir() -> None:
    """The other half. Removing PYTHONPATH only works because this exists.

    pytest resolves these RELATIVE TO ROOTDIR. Under mutation, rootdir is
    `mutants/`, so they resolve to the instrumented copies; normally they
    resolve to the real tree. One setting, correct in both, with no caller
    required to know which situation they are in.
    """
    configured = pyproject()["tool"]["pytest"]["ini_options"]["pythonpath"]  # type: ignore[index]
    assert configured == REQUIRED_PYTHONPATH, (
        f"expected pythonpath {REQUIRED_PYTHONPATH}, found {configured}. "
        "Without it, dropping PYTHONPATH from the mutation job leaves the "
        "package unimportable and the whole suite fails to collect."
    )


def test_every_import_path_entry_is_relative() -> None:
    """An absolute entry would reintroduce the bug through the other door.

    `pythonpath = ["/abs/path/src"]` pins the original tree no matter what
    rootdir pytest chose, which is precisely the behaviour that made the score
    meaningless. Relative is not a style preference here; it is the mechanism.
    """
    configured = pyproject()["tool"]["pytest"]["ini_options"]["pythonpath"]  # type: ignore[index]
    absolute = [entry for entry in configured if pathlib.PurePath(entry).is_absolute()]
    assert absolute == [], (
        f"absolute pythonpath entries: {absolute}. These survive a rootdir "
        "change, so mutation would score the original tree again."
    )


def test_the_mutation_step_still_carries_the_warning_that_explains_why() -> None:
    """The comment is load-bearing.

    The removed line looks correct — it is correct in every other job in this
    repository. Without the explanation sitting next to it, the obvious fix for
    a future import error is to add it back, and the gate silently returns to
    measuring nothing while still reporting a number.
    """
    body = TESTING_WORKFLOW.read_text(encoding="utf-8")
    assert "THIS STEP MUST NOT SET PYTHONPATH" in body, (
        "the warning above the mutation step is gone. It is the only thing "
        "telling the next person why the obvious line is absent."
    )
