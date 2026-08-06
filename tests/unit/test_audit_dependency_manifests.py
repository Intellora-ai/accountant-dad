"""A dependency manifest can exist in this repository and be audited by nobody.

THE MEASURED HOLE, not a hypothetical one. `dependency scan` runs pip-audit
against `requirements-ci.txt` and against `pyproject.toml`'s five declared
dependencies. There are THREE requirements manifests. The other two are
installed by four other CI jobs and have never been passed to pip-audit:

    requirements-engine1.txt       docling  transformers  torch
                                   torchvision  timm  pypdfium2
    requirements-engine1-ocr.txt   the OCR stack

Six pinned distributions, `torch` among them, entered every CI environment with
zero advisory scanning. Nothing was wrong with what the gate audited. The defect
is that the set it audits was written down somewhere nothing compares against
the filesystem, so the gap could not be seen from inside the gate.

WHAT THESE TESTS GUARD, AND WHAT THEY DELIBERATELY DO NOT.

They guard the TOOLING: that the manifest set is derived from the tree, that a
manifest the audit skipped is refused, and that the six unaudited pins are now
inside the derived set. They do NOT assert that `.github/workflows/security.yml`
calls the tooling — wiring a workflow is a `.github` change, which is made
deliberately and separately, and a test that failed until that landed would be
a red suite guarding somebody else's edit rather than this one.

THE ANTI-HOLLOW PROBLEM AND HOW IT IS HANDLED. Every assertion below quantifies
over a DERIVED set. If the derivation silently returned nothing, they would all
pass over an empty collection and prove nothing at all. So the two Engine 1
manifests and the six pins are named as ANCHORS — not as the list under test,
but as the minimum the derivation must find before any other assertion here
means anything.
"""

from __future__ import annotations

import pathlib

import audit_dependency_manifests as audit
import pytest
from authored_source import authored_path

REPO = pathlib.Path(__file__).resolve()
while not (REPO / "requirements-ci.txt").is_file():
    if REPO.parent == REPO:
        raise AssertionError(
            "no ancestor of this test carries requirements-ci.txt; the repository root "
            "cannot be located, so nothing below could read a real manifest"
        )
    REPO = REPO.parent

#: The manifests the pre-existing `dependency scan` step has never audited.
#: Anchors, not the list under test.
NEVER_AUDITED = (
    pathlib.Path("requirements-engine1.txt"),
    pathlib.Path("requirements-engine1-ocr.txt"),
)

#: The distributions those two manifests pin. Every one of them entered CI with
#: no advisory scanning. `torch` is the reason this is HIGH and not tidiness.
NEVER_AUDITED_PINS = frozenset(
    {"docling", "transformers", "torch", "torchvision", "timm", "pypdfium2"}
)


# ── the derivation actually reads the real tree ─────────────────────────


def test_the_derivation_finds_the_manifests_this_repository_really_has() -> None:
    """ANTI-HOLLOW ANCHOR. Every other test here quantifies over this set."""
    found = audit.manifests(REPO)
    assert found, "the manifest derivation returned nothing; every check here would be vacuous"
    assert pathlib.Path("requirements-ci.txt") in found
    for manifest in NEVER_AUDITED:
        assert manifest in found, (
            f"{manifest} exists in the tree and the derivation missed it. That file is "
            "installed by four CI jobs and audited by none."
        )


def test_the_six_pins_no_audit_has_ever_seen_are_inside_the_derived_set() -> None:
    """The exact measured exposure, named by distribution.

    Reads the pins off disk rather than listing versions here: a version literal
    in a test is a second source of truth that drifts from the manifest.
    """
    reachable = {
        name.lower().replace("_", "-")
        for manifest in audit.manifests(REPO)
        for name, _ in audit.pins(REPO / manifest)
    }
    missing = sorted(NEVER_AUDITED_PINS - reachable)
    assert not missing, (
        f"these pinned distributions are in no manifest the audit would reach: {missing}. "
        "They enter CI with no advisory scanning."
    )


def test_every_manifest_the_derivation_finds_actually_declares_pins() -> None:
    """A manifest that pins nothing cannot be audited, and must not be counted."""
    for manifest in audit.manifests(REPO):
        assert audit.pins(REPO / manifest), (
            f"{manifest} declares no exact pin; pip-audit would verify nothing over it"
        )


def test_the_declaration_sites_leave_no_dependency_file_uncovered() -> None:
    """The manifests plus pyproject. pyproject is audited by the pre-existing
    `pip-audit .` step, so the union is what must be complete, not this script
    alone."""
    sites = audit.declaration_sites(REPO)
    assert pathlib.Path(audit.PYPROJECT) in sites
    for manifest in audit.manifests(REPO):
        assert manifest in sites


# ── the gate: a skipped manifest is refused ─────────────────────────────


def _tree(root: pathlib.Path, files: dict[str, str]) -> pathlib.Path:
    for name, body in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
    return root


def test_a_manifest_the_audit_skipped_is_refused_by_name(tmp_path: pathlib.Path) -> None:
    """THE CORE GATE. This is the shape of the real defect: the audit ran, it
    passed, and one manifest was never handed to it."""
    _tree(
        tmp_path,
        {
            "requirements-ci.txt": "ruff==0.14.5\n",
            "requirements-engine1.txt": "torch==2.13.0\n",
        },
    )
    problems = audit.verify(tmp_path, ["requirements-ci.txt"])
    assert problems, "a manifest was skipped and the check reported no problem"
    assert any("requirements-engine1.txt" in problem for problem in problems), (
        f"the skipped manifest is not named in {problems}"
    )


def test_a_complete_audit_is_accepted(tmp_path: pathlib.Path) -> None:
    """The inverse, and it is not decoration. A verifier that refused everything
    would make the test above pass while guarding nothing."""
    _tree(
        tmp_path,
        {
            "requirements-ci.txt": "ruff==0.14.5\n",
            "requirements-engine1.txt": "torch==2.13.0\n",
        },
    )
    assert audit.verify(tmp_path, ["requirements-ci.txt", "requirements-engine1.txt"]) == ()


def test_a_manifest_that_declares_no_pins_is_refused(tmp_path: pathlib.Path) -> None:
    """Emptying a manifest is the cheapest way to make an audit pass over it."""
    _tree(
        tmp_path,
        {
            "requirements-ci.txt": "ruff==0.14.5\n",
            "requirements-empty.txt": "# every line is a comment\n\n",
        },
    )
    problems = audit.verify(tmp_path, ["requirements-ci.txt", "requirements-empty.txt"])
    assert any("requirements-empty.txt" in problem for problem in problems), (
        f"a manifest pinning nothing was accepted: {problems}"
    )


def test_a_tree_with_no_manifest_at_all_is_refused_rather_than_passed(
    tmp_path: pathlib.Path,
) -> None:
    """Zero is not a pass. A tree with nothing to audit would otherwise sail
    through every loop and report success having verified nothing."""
    problems = audit.verify(tmp_path, [])
    assert problems, "a tree with no manifest was reported clean"
    assert "audited nothing" in problems[0]


def test_a_path_that_is_not_a_manifest_cannot_be_reported_as_audited(
    tmp_path: pathlib.Path,
) -> None:
    """The audit and the repository must agree about what exists. A caller that
    invents a filename is reporting on something that is not there."""
    _tree(tmp_path, {"requirements-ci.txt": "ruff==0.14.5\n"})
    problems = audit.verify(tmp_path, ["requirements-ci.txt", "requirements-imaginary.txt"])
    assert any("requirements-imaginary.txt" in problem for problem in problems), (
        f"a path that is not in the tree was accepted as audited: {problems}"
    )


def test_a_copy_of_the_tree_is_not_mistaken_for_the_tree(tmp_path: pathlib.Path) -> None:
    """`mutants/` is mutmut's working copy and carries a duplicate of every
    manifest. Counting those would audit the same pins twice under paths that do
    not exist on a clean checkout, and would make `--verify` demand files nobody
    can produce."""
    _tree(
        tmp_path,
        {
            "requirements-ci.txt": "ruff==0.14.5\n",
            "mutants/requirements-ci.txt": "ruff==0.14.5\n",
            ".venv/requirements-ci.txt": "ruff==0.14.5\n",
        },
    )
    assert audit.manifests(tmp_path) == (pathlib.Path("requirements-ci.txt"),)


def test_a_manifest_in_a_subdirectory_is_still_found(tmp_path: pathlib.Path) -> None:
    """A root-only glob would miss it in silence — the same failure mode this
    whole file exists to remove, one directory down."""
    _tree(
        tmp_path,
        {
            "requirements-ci.txt": "ruff==0.14.5\n",
            "deploy/requirements-runtime.txt": "torch==2.13.0\n",
        },
    )
    assert pathlib.Path("deploy/requirements-runtime.txt") in audit.manifests(tmp_path)


# ── the pin parser ──────────────────────────────────────────────────────


def test_only_an_exact_pin_counts(tmp_path: pathlib.Path) -> None:
    """A range is not a pin and cannot be checked against a single version."""
    manifest = tmp_path / "requirements-mixed.txt"
    manifest.write_text(
        "# a comment\n"
        "\n"
        "exact==1.2.3\n"
        "ranged>=1.0\n"
        "compatible~=2.0\n"
        "marked==4.5.6 ; python_version >= '3.12'\n"
        "  spaced == 7.8.9\n",
        encoding="utf-8",
    )
    assert audit.pins(manifest) == (
        ("exact", "1.2.3"),
        ("marked", "4.5.6"),
        ("spaced", "7.8.9"),
    )


# ── the command line ────────────────────────────────────────────────────


def test_list_prints_every_manifest_and_verify_agrees_with_it(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The two modes must describe the same repository, or the shell loop that
    consumes one and feeds the other is comparing different things."""
    _tree(
        tmp_path,
        {
            "requirements-ci.txt": "ruff==0.14.5\n",
            "requirements-engine1.txt": "torch==2.13.0\n",
        },
    )
    monkeypatch.chdir(tmp_path)

    assert audit.cli(["--list"]) == 0
    listed = capsys.readouterr().out.split()
    assert sorted(listed) == ["requirements-ci.txt", "requirements-engine1.txt"]

    assert audit.cli(["--verify", *listed]) == 0
    assert audit.cli(["--verify", listed[0]]) == 1


def test_the_command_line_refuses_an_unknown_mode(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Never fail silently (Law 11). An unrecognised argument must not be read
    as 'audit nothing, exit 0'."""
    monkeypatch.chdir(tmp_path)
    assert audit.cli([]) == audit.USAGE_EXIT_CODE
    assert audit.cli(["--audit-everything-please"]) == audit.USAGE_EXIT_CODE
    #: Distinct from 1 on purpose. A caller that mistyped a flag has learned
    #: nothing about its dependencies and must not be told it found a problem.
    assert audit.USAGE_EXIT_CODE != 1


# ── the installed tree, not the manifest ────────────────────────────────
#
# Auditing manifests proves things about what was ASKED FOR. F-023 measured the
# other half on this repository's own environment: 13 distributions installed
# and reachable from no manifest at all, every one from the OCR tree. Importable,
# unpinned, audited by nothing.
#
# These tests drive the closure with FABRICATED graphs rather than the real
# environment. A test that asserted "this machine has zero orphans" would be red
# on any developer box that ever installed the OCR stack, and a test that
# asserted "this machine has thirteen" would go red the moment somebody cleaned
# it. Neither states a property of the repository. The cleanliness assertion
# belongs where the environment is built from the manifests, which is CI.


def test_a_transitive_dependency_is_reachable_and_not_an_orphan() -> None:
    """The check must be reachability, not membership. Demanding that every
    installed distribution be PINNED would fail on every correct environment,
    because a manifest legitimately pulls dependencies it does not name."""
    graph = {
        "docling": frozenset({"docling-slim"}),
        "docling-slim": frozenset({"pydantic"}),
        "pydantic": frozenset(),
    }
    assert audit.unreachable(frozenset({"docling"}), graph) == ()


def test_an_installed_distribution_no_manifest_reaches_is_reported() -> None:
    """The measured defect: a package pip installed once and nothing removed."""
    graph = {
        "docling": frozenset({"docling-slim"}),
        "docling-slim": frozenset(),
        "python-bidi": frozenset(),
    }
    assert audit.unreachable(frozenset({"docling"}), graph) == ("python-bidi",)


def test_the_installer_footprint_is_not_reported_as_an_orphan() -> None:
    """pip, setuptools and wheel are in every environment pip built and are
    required by no manifest. Reporting them would make this guard fire on a
    correct environment, and a guard that does that gets switched off."""
    graph: dict[str, frozenset[str]] = {
        "pip": frozenset(),
        "setuptools": frozenset(),
        "wheel": frozenset(),
    }
    assert audit.unreachable(frozenset(), graph) == ()


def test_a_dependency_cycle_does_not_hang_the_closure() -> None:
    """Real metadata contains cycles. A naive walk never terminates on one."""
    graph = {
        "a": frozenset({"b"}),
        "b": frozenset({"a", "c"}),
        "c": frozenset({"b"}),
        "stray": frozenset(),
    }
    assert audit.unreachable(frozenset({"a"}), graph) == ("stray",)


def test_a_requirement_that_is_not_installed_is_not_walked() -> None:
    """An environment cannot be judged on a package it does not have. Walking a
    name absent from the graph would invent reachability."""
    graph = {"a": frozenset({"absent"}), "stray": frozenset()}
    assert audit.unreachable(frozenset({"a"}), graph) == ("stray",)


def test_names_are_compared_after_pep_503_normalisation() -> None:
    """`PyYAML`, `pyyaml` and `py_yaml` are one distribution. Comparing raw
    strings would report a pinned package as an orphan because the manifest
    capitalised it differently."""
    assert audit.canonical("PyYAML") == "pyyaml"
    assert audit.canonical("ruamel.yaml") == "ruamel-yaml"
    assert audit.canonical("opencv_python") == "opencv-python"
    graph: dict[str, frozenset[str]] = {"pyyaml": frozenset()}
    assert audit.unreachable(frozenset({audit.canonical("PyYAML")}), graph) == ()


def test_an_extra_and_a_marker_do_not_become_part_of_the_name() -> None:
    """`docling-slim[standard] (>=2.1) ; extra == "ocr"` names ONE distribution.
    Parsing the whole string as a name would make every such dependency
    unreachable and the guard would scream on a correct tree."""
    graph = {
        "docling": frozenset({"docling-slim"}),
        "docling-slim": frozenset(),
    }
    assert audit.unreachable(frozenset({"docling"}), graph) == ()
    assert audit._required_names('docling-slim[standard] (>=2.1) ; extra == "ocr"') == (
        "docling-slim"
    )
    assert audit._required_names("Torch>=2.0") == "torch"


def test_the_real_environment_adapter_actually_reads_metadata() -> None:
    """ANTI-HOLLOW. Every closure test above runs on a fabricated graph. If the
    adapter that builds the real one returned nothing, the command line would
    report a clean environment while looking at an empty set."""
    graph = audit.installed_requirements()
    assert graph, "no installed distribution was found; the orphan check would be vacuous"
    assert "pytest" in graph, f"pytest is running yet absent from {len(graph)} distributions"
    assert any(graph[name] for name in graph), (
        "not one distribution declared a requirement; the graph has no edges and "
        "every package would look like an orphan"
    )


# ── the shell entry point is wired to the derivation ────────────────────


def test_the_shell_entry_point_derives_the_list_audits_it_and_verifies_it() -> None:
    """A wiring test, not a style check.

    The split — derivation in Python, pip-audit in shell — is only safe while
    the shell actually asks for the list, runs the auditor over it, and hands
    back what it ran. Any one of those three missing turns the gate hollow in a
    way no Python test could see.

    Read through `authored_path` so that under mutation this reads the file this
    repository wrote rather than whatever the interpreter is running.
    """
    entry = authored_path(audit).with_suffix(".sh")
    assert entry.is_file(), f"the shell entry point is missing at {entry}"
    text = entry.read_text(encoding="utf-8")

    assert "--list" in text, "the shell does not ask for the derived manifest set"
    assert "pip-audit" in text, "the shell never invokes the auditor"
    assert "--strict" in text, (
        "pip-audit without --strict skips a dependency it cannot resolve, and a "
        "skipped package is an unaudited package wearing a pass"
    )
    assert "--verify" in text, (
        "the shell audits without proving it covered every manifest; a loop that "
        "exits early would be invisible"
    )
    assert "--orphans" in text, (
        "the shell audits the manifests and never looks at what is actually "
        "installed, which is the half F-023 measured at 13 distributions"
    )
    assert "set -euo pipefail" in text, "an unset variable or a failed command would pass silently"
