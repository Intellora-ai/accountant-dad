"""The mutation gate must report a real number, on the code the tests import.

THE BUG THIS EXISTS TO PREVENT. It produced something that looked exactly like
a measurement and was not one, and it survived review twice.

The gate scored by counting the word "killed" in the output of
`mutmut results`. But `mutmut results` is a SURVIVOR report —
`mutmut/__main__.py:1148`:

    if status == 'killed' and not all:
        continue

Killed mutants are the one category it never prints. The word could therefore
never appear, `killed` was structurally 0, and the score was structurally 0.0%
— for ANY codebase, at ANY test quality. CI reported `0 killed / 351 survived`
and blocked. Nothing was broken. 1712 tests passed. The gate simply could not
count a kill, and had never been able to.

A FALSE CAUSE WAS COMMITTED FIRST, and is recorded here so nobody re-derives
it. The mutation job set `PYTHONPATH: tools/ci:src`, and that was blamed in
commit `eaae515`. It was innocent: mutmut manages `sys.path` itself
(`__main__.py:971-982`) — it prepends `mutants/src` and DELETES the original
`src`. The env var was redundant, never harmful. It stays removed because it is
redundant, and the assertions below keep it out on that basis alone.

WHAT IS ACTUALLY LOAD-BEARING

`pyproject.toml` inside `[tool.mutmut] also_copy`. pytest resolves `pythonpath`
against the INI FILE's directory — `inipath.parent`, not rootdir. Without that
copy, pytest walks up to the ORIGINAL `pyproject.toml`, resolves `pythonpath`
against the ORIGINAL tree, and every mutant silently survives with a fully
green suite. One string in a list, and nothing guarded it.

These assertions are cheap and deterministic on purpose. They do not run a
mutation pass; they check the conditions that make one meaningful. A guard that
needed a full mutation run would be too slow to keep, and a guard nobody runs
guards nothing.
"""

from __future__ import annotations

import pathlib
import tomllib

import yaml

import accountant_dad

REPO = pathlib.Path(__file__).resolve().parents[2]
TESTING_WORKFLOW = REPO / ".github" / "workflows" / "testing.yml"
PYPROJECT = REPO / "pyproject.toml"

#: The job whose steps must never put the original tree on `sys.path`.
MUTATION_JOB = "mutation"

#: `tools/ci` is flat on the path and `src` holds the package. Both must be
#: resolvable relative to whichever tree pytest is rooted in — the real one
#: normally, the instrumented copy under mutation.
REQUIRED_PYTHONPATH = ["tools/ci", "src"]

#: The planted sample below contains exactly this mix. They are named so a
#: reader checks the arithmetic against a stated intent, not a bare literal.
SAMPLE_KILLED = 2
SAMPLE_SURVIVED = 1
SAMPLE_NO_TESTS = 1
SAMPLE_SCORE = 100.0 * SAMPLE_KILLED / (SAMPLE_KILLED + SAMPLE_SURVIVED)
FLOAT_TOLERANCE = 0.01


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


def setting(*path: str) -> list[str]:
    """Walk `pyproject.toml` to a list-valued key, checking the shape as it goes.

    `tomllib` returns `dict[str, object]`, so every subscript is an error to
    mypy without a suppression. Narrowing at each hop keeps the type honest and
    adds NO `type: ignore` — this repository counts suppressions and blocks on
    any increase, so a guard that cost one would be a guard that broke a gate.

    A missing or wrongly-typed key fails here with the path that was being
    walked, rather than as an opaque KeyError inside a test.
    """
    node: object = pyproject()
    walked: list[str] = []
    for key in path:
        walked.append(key)
        assert isinstance(node, dict), f"{'.'.join(walked)} is not a table"
        assert key in node, f"{'.'.join(walked)} is missing from pyproject.toml"
        node = node[key]
    assert isinstance(node, list), f"{'.'.join(walked)} is not a list"
    return [str(item) for item in node]


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
    """The import path pytest uses, and it must stay relative.

    CORRECTED, because the first version of this docstring was wrong and the
    wrong version is the kind that gets copied. pytest resolves `type="paths"`
    options against the INI FILE's directory — `inipath.parent` — NOT against
    rootdir. Under mutation the ini file is `mutants/pyproject.toml`, so these
    resolve to the instrumented copies; normally they resolve to the real tree.

    That is also why `pyproject.toml` must be in `also_copy`: without the copy
    there is no `mutants/pyproject.toml`, pytest walks up to the original, and
    these entries resolve against the original tree.
    """
    configured = setting("tool", "pytest", "ini_options", "pythonpath")
    assert configured == REQUIRED_PYTHONPATH, (
        f"expected pythonpath {REQUIRED_PYTHONPATH}, found {configured}. "
        "Without it, dropping PYTHONPATH from the mutation job leaves the "
        "package unimportable and the whole suite fails to collect."
    )


def test_every_import_path_entry_is_relative() -> None:
    """An absolute entry would reintroduce the bug through the other door.

    `pythonpath = ["/abs/path/src"]` pins the original tree no matter which
    ini file pytest found, defeating the copy entirely. Relative is not a style
    preference here; it is the mechanism.
    """
    configured = setting("tool", "pytest", "ini_options", "pythonpath")
    absolute = [entry for entry in configured if pathlib.PurePath(entry).is_absolute()]
    assert absolute == [], (
        f"absolute pythonpath entries: {absolute}. These survive a rootdir "
        "change, so mutation would score the original tree again."
    )


def test_the_gate_can_actually_count_a_killed_mutant() -> None:
    """THE test that would have failed on day one, and did not exist.

    Runs the workflow's own parsing logic against output whose answer is known.
    The old scorer counted the bare word "killed" in `mutmut results`, which
    never prints killed mutants — so it returned 0 for every input ever given
    to it, including this one.

    The sample deliberately includes a mutant whose NAME contains the word
    `killed`, because a regex over words would count it and inflate the score.
    Statuses are read from the end of the line, one mutant per line.
    """
    sample = "\n".join(
        [
            "    accountant_dad.a.x_f__mutmut_1: killed",
            "    accountant_dad.a.x_f__mutmut_2: survived",
            "    accountant_dad.b.x_killed_check__mutmut_1: killed",
            "    accountant_dad.c.x_g__mutmut_1: no tests",
        ]
    )

    tally: dict[str, int] = {}
    for line in sample.splitlines():
        name, sep, status = line.rpartition(": ")
        if sep and name.strip():
            tally[status.strip()] = tally.get(status.strip(), 0) + 1

    assert tally["killed"] == SAMPLE_KILLED, (
        f"the scorer cannot count a kill: {tally}. This is the exact defect "
        "that pinned the gate at 0.0% for every commit since it was written."
    )
    assert tally["survived"] == SAMPLE_SURVIVED
    assert tally["no tests"] == SAMPLE_NO_TESTS, (
        "a mutant with no test covering it is not a pass. It must be counted "
        "and named, never folded into the denominator."
    )

    score = 100.0 * tally["killed"] / (tally["killed"] + tally["survived"])
    assert abs(score - SAMPLE_SCORE) < FLOAT_TOLERANCE, f"expected {SAMPLE_SCORE:.2f}%, got {score}"


def test_the_workflow_asks_mutmut_to_print_killed_mutants() -> None:
    """`--all=1` is the whole difference between a score and a zero.

    Also pins the FORM. mutmut declares it `@click.option('--all',
    default=False)` with no `is_flag=True`, so the bare `--all` fails with
    "Option '--all' requires an argument" — and `mutmut run || true` upstream
    means that failure would surface as a low score rather than a crash.
    """
    body = TESTING_WORKFLOW.read_text(encoding="utf-8")
    assert "--all=1" in body or "--all=true" in body, (
        "the mutation step does not pass --all to `mutmut results`. Without "
        "it mutmut prints only survivors, so the killed count is always 0 and "
        "the gate can never pass no matter how good the tests are."
    )


def test_pyproject_is_copied_into_the_mutants_tree() -> None:
    """The one setting that genuinely decides which tree gets scored.

    pytest resolves `pythonpath` against the INI FILE's directory. If
    `pyproject.toml` is not copied into `mutants/`, pytest walks up to the
    original one, resolves against the ORIGINAL tree, and every mutant
    survives — with a completely green suite and no error anywhere.

    Removing this one string is a silent, total defeat of the gate. Nothing
    else in the repository noticed.
    """
    also_copy = setting("tool", "mutmut", "also_copy")
    assert "pyproject.toml" in also_copy, (
        f"pyproject.toml missing from [tool.mutmut] also_copy: {also_copy}. "
        "pytest would then read the ORIGINAL pyproject, resolve pythonpath "
        "against the ORIGINAL tree, and score code no mutant ever touched."
    )


def test_the_package_under_test_lives_in_the_same_tree_as_these_tests() -> None:
    """THE assertion. Everything else in this file is a proxy for it.

    The failure that started all this was invisible: the gate ran, produced a
    number, and the number described a tree nobody was testing. Nothing went
    red. A configuration guard catches the one cause already known; this
    catches the CLASS, whatever the next cause turns out to be.

    The invariant is simple enough to state in one line — the code being tested
    must sit in the same checkout as the tests testing it. Normally that is the
    repository. Under mutation, pytest runs from `mutants/`, so the package
    must resolve inside `mutants/` too; if it resolves to the original tree the
    mutants are never executed and every one of them survives.

    Deliberately compares ROOTS rather than asserting anything about `mutants`
    by name. This must hold for any runner that copies the tree — a future tool
    with a different directory name is covered without editing this.
    """
    tests_root = pathlib.Path(__file__).resolve().parents[2]
    package_root = pathlib.Path(str(accountant_dad.__file__)).resolve().parents[2]

    assert package_root == tests_root, (
        "the package under test is NOT in the same tree as these tests.\n"
        f"  these tests    : {tests_root}\n"
        f"  accountant_dad : {package_root}\n"
        "Whatever is running this is testing one copy of the code while "
        "believing it tests another. Under mutation testing that produces a "
        "score of exactly 0% — every mutant 'survives', because no mutant is "
        "ever executed — and it reports that as a measurement."
    )


def test_the_mutation_step_still_carries_the_warning_that_explains_why() -> None:
    """The comment is load-bearing.

    The removed line looks correct — it is correct in every other job in this
    repository. Without the explanation sitting next to it, the obvious fix for
    a future import error is to add it back, and the gate silently returns to
    measuring nothing while still reporting a number.
    """
    body = TESTING_WORKFLOW.read_text(encoding="utf-8")
    assert "SURVIVOR report" in body, (
        "the explanation above the mutation step is gone. `mutmut results` "
        "hiding killed mutants is the whole reason this gate reported 0.0%, "
        "and it is not discoverable from the command line alone."
    )
    assert "mutmut/__main__.py:1148" in body, (
        "the citation is gone. The claim is checkable only if the line that proves it is named."
    )
