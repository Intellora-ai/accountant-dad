"""The decision logic of the merge gate.

Faked ONLY at the I/O edge — the HTTP call and the clock. Everything else is the
real code path, because that is where a wrong verdict would come from.
"""

import io
import json
import time
import urllib.error
import urllib.request
from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING

import poll_checks
import pytest

if TYPE_CHECKING:
    from poll_checks import CheckRun

_EXPECTED_RETRY_CALLS = 2

WORKFLOW = """\
name: probe
on:
  push:
jobs:
  alpha:
    name: alpha
    runs-on: ubuntu-24.04
    steps:
      - run: exit 0
  beta:
    name: beta
    runs-on: ubuntu-24.04
    steps:
      - run: exit 0
"""


def workflows(tmp_path: Path) -> Path:
    directory = tmp_path / "wf"
    directory.mkdir()
    (directory / "w.yml").write_text(WORKFLOW, encoding="utf-8")
    return directory


def declared_file(tmp_path: Path, body: str = "") -> Path:
    """A declared-exceptions file. Empty by default: nothing is excused.

    Empty is the strict default on purpose. A test that wants an exception must
    ask for one explicitly, so no test can be accidentally lenient.
    """
    path = tmp_path / "declared.txt"
    path.write_text(body, encoding="utf-8")
    return path


def run_main(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    runs: list["CheckRun"],
    *,
    timeout_minutes: str = "1",
    declared: str = "",
) -> int:
    monkeypatch.setattr(poll_checks, "fetch_check_runs", lambda *_: runs)
    monkeypatch.setattr(time, "sleep", lambda _: None)
    monkeypatch.setenv("GITHUB_REPOSITORY", "o/r")
    monkeypatch.setenv("MERGE_GATE_SHA", "deadbeef")
    monkeypatch.setenv("GITHUB_TOKEN", "t")
    monkeypatch.setenv("MERGE_GATE_POLL_TIMEOUT_MINUTES", timeout_minutes)
    monkeypatch.setenv("MERGE_GATE_POLL_INTERVAL_SECONDS", "0")
    monkeypatch.setenv("MERGE_GATE_WORKFLOWS_DIR", str(workflows(tmp_path)))
    monkeypatch.setenv("MERGE_GATE_DECLARED_EXCEPTIONS", str(declared_file(tmp_path, declared)))
    return poll_checks.main()


def done(name: str, conclusion: str) -> "CheckRun":
    return {"id": 1, "name": name, "status": "completed", "conclusion": conclusion}


def test_all_success_passes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = run_main(monkeypatch, tmp_path, [done("alpha", "success"), done("beta", "success")])
    assert code == 0
    out = capsys.readouterr().out
    assert "all 2 gates accounted for" in out
    # Stricter than the old assertion: with no declared exceptions, BOTH gates
    # must be counted as passed and NONE as excused.
    assert "2 passed" in out
    assert "0 red by declaration" in out


@pytest.mark.parametrize(
    "conclusion",
    ["failure", "cancelled", "skipped", "timed_out", "neutral", "action_required", "stale"],
)
def test_every_non_success_conclusion_blocks(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    conclusion: str,
) -> None:
    # "skipped" is the one GitHub natively treats as passing. It must not here.
    # No declared exceptions, so every one of these is an UNDECLARED failure.
    code = run_main(monkeypatch, tmp_path, [done("alpha", "success"), done("beta", conclusion)])
    assert code == 1
    out = capsys.readouterr().out
    assert "BLOCKED - a gate that is NOT declared a placeholder did not succeed" in out
    assert conclusion.upper() in out


def test_a_declared_gate_is_excused_but_an_undeclared_one_still_blocks(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # The whole point of the mechanism, through main() rather than the pure
    # function: one excused red must not excuse a second, undeclared red.
    code = run_main(
        monkeypatch,
        tmp_path,
        [done("alpha", "failure"), done("beta", "failure")],
        declared="PH-90 | alpha | @o | P2 | schema exists | no artifact exists yet\n",
    )
    assert code == 1
    out = capsys.readouterr().out
    assert "EXCUSED alpha" in out
    assert "FAILURE beta" in out


def test_a_declared_gate_that_passes_blocks_as_stale(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Without this the list rots: a gate that starts passing stays excused
    # forever and silently covers a later regression.
    code = run_main(
        monkeypatch,
        tmp_path,
        [done("alpha", "success"), done("beta", "success")],
        declared="PH-90 | alpha | @o | P2 | schema exists | no artifact exists yet\n",
    )
    assert code == 1
    assert "STALE" in capsys.readouterr().out


def test_a_gate_that_never_reports_blocks_as_a_timeout(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # beta never reports at all. Absence must never be read as success.
    code = run_main(monkeypatch, tmp_path, [done("alpha", "success")], timeout_minutes="0")
    assert code == 1
    out = capsys.readouterr().out
    assert "timed out" in out
    assert "beta" in out


def test_incomplete_check_is_not_treated_as_finished(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    still_running: CheckRun = {"id": 2, "name": "beta", "status": "in_progress", "conclusion": None}
    code = run_main(
        monkeypatch, tmp_path, [done("alpha", "success"), still_running], timeout_minutes="0"
    )
    assert code == 1
    assert "in_progress" in capsys.readouterr().out


def test_a_transient_api_error_retries_rather_than_deciding(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # An API blip must never be allowed to resolve the gate either way.
    calls = {"n": 0}

    def flaky(*_: object) -> list["CheckRun"]:
        calls["n"] += 1
        if calls["n"] == 1:
            raise urllib.error.URLError("boom")
        return [done("alpha", "success"), done("beta", "success")]

    monkeypatch.setattr(poll_checks, "fetch_check_runs", flaky)
    monkeypatch.setattr(time, "sleep", lambda _: None)
    monkeypatch.setenv("GITHUB_REPOSITORY", "o/r")
    monkeypatch.setenv("MERGE_GATE_SHA", "deadbeef")
    monkeypatch.setenv("GITHUB_TOKEN", "t")
    monkeypatch.setenv("MERGE_GATE_POLL_TIMEOUT_MINUTES", "1")
    monkeypatch.setenv("MERGE_GATE_POLL_INTERVAL_SECONDS", "0")
    monkeypatch.setenv("MERGE_GATE_WORKFLOWS_DIR", str(workflows(tmp_path)))
    monkeypatch.setenv("MERGE_GATE_DECLARED_EXCEPTIONS", str(declared_file(tmp_path)))

    assert poll_checks.main() == 0
    assert "api error, retrying" in capsys.readouterr().out
    assert calls["n"] == _EXPECTED_RETRY_CALLS


class FakeResponse(io.BytesIO):
    def __init__(self, payload: object, link: str = "") -> None:
        super().__init__(json.dumps(payload).encode())
        self.headers = {"Link": link}

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def test_fetch_reads_check_runs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        urllib.request,
        "urlopen",
        lambda *_a, **_k: FakeResponse({"check_runs": [{"id": 1, "name": "alpha"}]}),
    )
    runs = poll_checks.fetch_check_runs("o/r", "sha", "tok")
    assert [r["name"] for r in runs] == ["alpha"]


def test_fetch_follows_pagination(monkeypatch: pytest.MonkeyPatch) -> None:
    pages: Iterator[FakeResponse] = iter(
        [
            FakeResponse(
                {"check_runs": [{"id": 1, "name": "alpha"}]},
                link=f'<{poll_checks.API_ROOT}/next>; rel="next"',
            ),
            FakeResponse({"check_runs": [{"id": 2, "name": "beta"}]}),
        ]
    )
    monkeypatch.setattr(urllib.request, "urlopen", lambda *_a, **_k: next(pages))
    runs = poll_checks.fetch_check_runs("o/r", "sha", "tok")
    assert sorted(str(r["name"]) for r in runs) == ["alpha", "beta"]


def test_fetch_refuses_an_offsite_pagination_url(monkeypatch: pytest.MonkeyPatch) -> None:
    # The Link header is remote input. A redirect to an attacker host must not be followed.
    monkeypatch.setattr(
        urllib.request,
        "urlopen",
        lambda *_a, **_k: FakeResponse(
            {"check_runs": []}, link='<https://evil.example/x>; rel="next"'
        ),
    )
    with pytest.raises(SystemExit):
        poll_checks.fetch_check_runs("o/r", "sha", "tok")


def test_fetch_tolerates_a_malformed_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        urllib.request, "urlopen", lambda *_a, **_k: FakeResponse(["not", "a", "dict"])
    )
    assert poll_checks.fetch_check_runs("o/r", "sha", "tok") == []
