"""`KNOWN_FAILURES.md` may not say something this repository contradicts.

WHY THIS FILE EXISTS. Three of the tracker's claims were measured by hand on
2026-08-06 and two were false — F-024 said the repository does not build while
`Exclusion` imports fine, and F-026 said 24 commits carry no CI evidence while
the branch tip was pushed. Both had been true when written. Nothing in the
repository could contradict either one, so both survived the fix they described
and one was then carried into a root-cause analysis as evidence.

TWO HALVES, AND BOTH ARE NEEDED.

    the tracker is WELL FORMED   every entry has an identifier nobody else
                                 uses, a status, and exactly one predicate
                                 block whose verbs are in the closed set

    the tracker is TRUE          every predicate holds against the tree

The first half is what stops the next entry being written unverifiable: an
entry with no predicate does not parse, so it cannot be added quietly.

THE GUARD IS SHOWN REFUSING. `test_an_entry_that_lies_about_the_repository_
turns_this_test_red` rewrites a true entry into a false one and asserts the
verifier reports it, and eleven more tests feed the parser a malformed tracker
and require the named refusal. A guard never seen refusing is unproven (§J.1),
and this one guards a file whose whole failure mode is looking fine.
"""

from __future__ import annotations

import re
import runpy
import sys
from pathlib import Path

import first_party
import pytest
import verify_tracker
from authored_source import running_path
from verify_tracker import (
    ARITY,
    CHECK_LANGUAGE,
    FEWEST_ENTRIES_THAT_CAN_BE_REAL,
    FEWEST_WORDS_IN_A_REASON,
    SETTLED,
    STATES,
    TRACKER,
    UNVERIFIABLE,
    Check,
    TrackerDefectError,
    Verdict,
    counted_totals,
    declared_totals,
    entries_of,
    findings,
    parse,
    tracker_path,
    verdict,
)

# ═══════════════════════════════════════════════════════════════════════════
# A minimal, well-formed tracker. Every malformed-input test starts from this
# and breaks exactly one thing, so a refusal is attributable to that one thing.
# ═══════════════════════════════════════════════════════════════════════════
WELL_FORMED = """# KNOWN_FAILURES.md

```totals
entries=1 predicates=1 unverifiable=0
```

## F-001 · A title

| | |
|---|---|
| **Severity** | HIGH |
| **Status** | `OPEN` · ⬜ nothing has moved |

```check
exists pyproject.toml
```
"""


def a_tracker(*, body: str) -> str:
    """The well-formed tracker with its single entry replaced."""
    return WELL_FORMED[: WELL_FORMED.index("## F-001")] + body


ONE_ENTRY = """## F-001 · A title

| | |
|---|---|
| **Status** | `{state}` · {status} |

```check
{check}
```
"""


def an_entry(*, state: str = "OPEN", status: str = "prose", check: str) -> str:
    """One well-formed entry, with exactly the field under test varied."""
    return ONE_ENTRY.format(state=state, status=status, check=check)


# ═══════════════════════════════════════════════════════════════════════════
# THE REAL FILE — is it well formed, and is it true?
# ═══════════════════════════════════════════════════════════════════════════


@pytest.fixture(scope="module")
def tracker_text() -> str:
    return tracker_path().read_text(encoding="utf-8")


def test_the_tracker_parses_and_describes_the_file_it_claims_to(tracker_text: str) -> None:
    """A parser that silently matched nothing would report no lie either."""
    entries = entries_of(tracker_text)
    assert len(entries) >= FEWEST_ENTRIES_THAT_CAN_BE_REAL, (
        f"only {len(entries)} entries parsed out of {TRACKER}. Either the file shrank or "
        "the parser stopped recognising headings — and a parser that recognises nothing "
        "reports nothing wrong."
    )


def test_every_entry_carries_at_least_one_check(tracker_text: str) -> None:
    for entry in entries_of(tracker_text):
        assert entry.checks, f"{entry.identifier} declares no check"


def test_no_two_entries_share_an_identifier(tracker_text: str) -> None:
    """The F-026 collision: two entries under one number, cited from two files."""
    identifiers = [entry.identifier for entry in entries_of(tracker_text)]
    assert len(identifiers) == len(set(identifiers)), sorted(
        identifier for identifier in identifiers if identifiers.count(identifier) > 1
    )


def test_no_entry_says_anything_the_repository_contradicts(tracker_text: str) -> None:
    """THE POINT OF THE FILE. Every predicate, evaluated against the tree."""
    entries = entries_of(tracker_text)
    broken = [found for found in findings(entries) if not found.holds]
    assert not broken, "\n".join(
        f"{TRACKER}:{found.check.line} {found.identifier} — claims `{found.check}`, "
        f"but {found.detail}"
        for found in broken
    )


def test_every_settled_entry_carries_a_mechanical_predicate(tracker_text: str) -> None:
    """`CLOSED` is a claim the tree has to be able to refuse."""
    for entry in entries_of(tracker_text):
        if not entry.settled:
            continue
        assert any(check.mechanical for check in entry.checks), (
            f"{entry.identifier} is {SETTLED} but every check is {UNVERIFIABLE}"
        )


def test_no_check_proves_an_entry_out_of_the_tracker_itself(tracker_text: str) -> None:
    for entry in entries_of(tracker_text):
        for check in entry.checks:
            if not check.mechanical:
                continue
            assert Path(check.arguments[0]) != Path(TRACKER), (
                f"{entry.identifier} cites {TRACKER}: circular"
            )


def test_every_unverifiable_admission_says_why(tracker_text: str) -> None:
    for entry in entries_of(tracker_text):
        for check in entry.checks:
            if check.mechanical:
                continue
            reason = " ".join(check.arguments)
            assert len(reason.split()) >= FEWEST_WORDS_IN_A_REASON, (
                f"{entry.identifier}'s {UNVERIFIABLE} reason is {reason!r} — too short to "
                "tell a reader what would have to change for it to become checkable"
            )


def test_the_files_own_self_count_is_the_count(tracker_text: str) -> None:
    """A summary nobody recomputes is the next thing in this file to go stale."""
    assert declared_totals(tracker_text) == counted_totals(entries_of(tracker_text))


def test_every_verdict_is_true_or_a_stated_unverifiable(tracker_text: str) -> None:
    entries = entries_of(tracker_text)
    results = findings(entries)
    false = [entry.identifier for entry in entries if verdict(entry, results) is Verdict.FALSE]
    assert not false, false


# ═══════════════════════════════════════════════════════════════════════════
# THE GUARD, SHOWN REFUSING
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    ("verb", "lie", "expected"),
    [
        ("exists", "exists {0}.this-path-was-never-in-the-tree", "is not there"),
        ("defines", "defines {0} ThisSymbolWasNeverWritten", "does not define"),
        ("contains", 'contains {0} "this literal is nowhere in that file"', "does not contain"),
    ],
)
def test_an_entry_that_lies_about_the_repository_turns_this_test_red(
    tracker_text: str, verb: str, lie: str, expected: str
) -> None:
    """Flip one TRUE entry into a false claim; the verifier must name it.

    Against the REAL file and the REAL tree, with one line replaced — so the
    thing shown refusing is the thing that runs, not a paraphrase of it. Only
    the tampered entry may be reported: a guard that reddens about everything
    tells you nothing about the line you changed.
    """
    entries = entries_of(tracker_text)
    honest = next(
        entry
        for entry in entries
        if verdict(entry, findings(entries)) is Verdict.TRUE
        and any(check.verb == verb for check in entry.checks)
    )
    truthful = next(check for check in honest.checks if check.verb == verb)

    lines = tracker_text.splitlines()
    lines[truthful.line - 1] = lie.format(truthful.arguments[0])
    tampered = entries_of("\n".join(lines))

    broken = [found for found in findings(tampered) if not found.holds]

    assert [found.identifier for found in broken] == [honest.identifier]
    assert expected in broken[0].detail
    assert verdict(honest, broken) is Verdict.FALSE


def test_the_guard_notices_the_tree_changing_and_not_only_the_claim(
    tracker_text: str, tmp_path: Path
) -> None:
    """The mirror of the test above, and the direction that actually bites.

    A claim goes stale because the REPOSITORY moves under it, not because
    somebody edits the claim. So: take a real entry, reproduce the one file its
    predicate names, prove it holds — then rename the thing away and prove it
    stops holding.
    """
    entry = next(
        candidate
        for candidate in entries_of(tracker_text)
        if len(candidate.checks) == 1 and candidate.checks[0].verb == "defines"
    )
    check = entry.checks[0]
    path, name = check.arguments
    copy = tmp_path / path
    copy.parent.mkdir(parents=True, exist_ok=True)
    original = (first_party.repo_root() / path).read_text(encoding="utf-8")
    copy.write_text(original, encoding="utf-8")

    assert all(found.holds for found in findings((entry,), tmp_path))

    copy.write_text(original.replace(f"def {name}", "def renamed_away"), encoding="utf-8")
    broken = [found for found in findings((entry,), tmp_path) if not found.holds]
    assert [found.identifier for found in broken] == [entry.identifier]
    assert f"does not define {name}" in broken[0].detail


def test_restoring_the_tampered_line_makes_the_same_entry_true_again(
    tracker_text: str,
) -> None:
    """The other half of §J.5: the red must come from the change, not the tree."""
    entries = entries_of(tracker_text)
    honest = next(
        entry
        for entry in entries
        if verdict(entry, findings(entries)) is Verdict.TRUE
        and any(check.verb == "exists" for check in entry.checks)
    )
    truthful = next(check for check in honest.checks if check.verb == "exists")

    lines = tracker_text.splitlines()
    original = lines[truthful.line - 1]
    lines[truthful.line - 1] = f"exists {truthful.arguments[0]}.never-in-the-tree"
    assert [found for found in findings(entries_of("\n".join(lines))) if not found.holds]

    lines[truthful.line - 1] = original
    assert not [found for found in findings(entries_of("\n".join(lines))) if not found.holds]


def test_the_verifier_reports_zero_contradictions_on_the_unmodified_tree() -> None:
    """The other direction: no false alarm, or the test above proves nothing."""
    assert verify_tracker.contradicted() == ()


def test_a_new_entry_with_no_check_block_is_refused() -> None:
    """The rule that stops the NEXT entry being written unverifiable."""
    body = "## F-002 · Added without a predicate\n\n| **Status** | `OPEN` · ⬜ new |\n"
    with pytest.raises(TrackerDefectError, match=r"0 ```check block\(s\)"):
        parse(a_tracker(body=body))


def test_a_second_check_block_in_one_entry_is_refused() -> None:
    body = an_entry(check="exists pyproject.toml")
    with pytest.raises(TrackerDefectError, match=r"2 ```check block\(s\)"):
        parse(a_tracker(body=body) + "\n```check\nexists pyproject.toml\n```\n")


def test_an_entry_with_no_status_row_is_refused() -> None:
    body = "## F-002 · No status\n\n```check\nexists pyproject.toml\n```\n"
    with pytest.raises(TrackerDefectError, match=r"has no `\| \*\*Status\*\* \|` row"):
        parse(a_tracker(body=body))


def test_a_heading_that_is_neither_an_entry_nor_a_declared_section_is_refused() -> None:
    with pytest.raises(TrackerDefectError, match="neither an entry heading"):
        parse(a_tracker(body="## Some new section\n\ntext\n"))


def test_a_duplicate_identifier_is_refused() -> None:
    entry = an_entry(check="exists pyproject.toml")
    with pytest.raises(TrackerDefectError, match="F-001 is already used"):
        parse(a_tracker(body=entry + "\n" + entry))


def test_an_unknown_verb_is_refused_by_name() -> None:
    body = an_entry(check="probably-fine pyproject.toml")
    with pytest.raises(TrackerDefectError, match="unknown check verb 'probably-fine'"):
        parse(a_tracker(body=body))


@pytest.mark.parametrize(
    "check",
    ["exists", "exists a b", "defines a", "contains a", "not-defines a b c"],
)
def test_a_verb_given_the_wrong_number_of_arguments_is_refused(check: str) -> None:
    body = an_entry(check=check)
    with pytest.raises(TrackerDefectError, match="argument"):
        parse(a_tracker(body=body))


def test_an_entry_proved_out_of_the_tracker_itself_is_refused() -> None:
    body = an_entry(check=f'contains {TRACKER} "OPEN"')
    with pytest.raises(TrackerDefectError, match="names the tracker itself"):
        parse(a_tracker(body=body))


def test_a_path_that_leaves_the_repository_is_refused(tmp_path: Path) -> None:
    body = an_entry(check="exists ../etc/passwd")
    entries = entries_of(a_tracker(body=body))
    with pytest.raises(TrackerDefectError, match="leaves the repository"):
        findings(entries, tmp_path)


def test_a_settled_entry_may_not_be_retired_behind_unverifiable() -> None:
    """The escape hatch's one closed door.

    Without this, every entry in the file could be retired by declaring it
    CLOSED and unverifiable in the same breath — which is the shape the whole
    guard exists to refuse.
    """
    body = an_entry(
        state=SETTLED,
        status="✅ landed 2026-08-06",
        check=f"{UNVERIFIABLE} it would be inconvenient to check this one",
    )
    with pytest.raises(TrackerDefectError, match=f"recorded {SETTLED}"):
        parse(a_tracker(body=body))


# ═══════════════════════════════════════════════════════════════════════════
# THE STATE TOKEN — the half of a status a program can read
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("state", STATES)
def test_every_declared_state_parses_and_only_closed_is_settled(state: str) -> None:
    entry = entries_of(a_tracker(body=an_entry(state=state, check="exists pyproject.toml")))[0]
    assert entry.state == state
    assert entry.settled is (state == SETTLED)


def test_a_status_row_written_without_a_state_token_is_refused() -> None:
    """The old free-prose form, refused by name rather than skipped.

    Skipping it would report "this entry has no status" for an entry that
    plainly has one, sending the reader to the wrong defect.
    """
    body = (
        "## F-001 · A title\n\n| **Status** | ⬜ OPEN |\n\n```check\nexists pyproject.toml\n```\n"
    )
    with pytest.raises(TrackerDefectError, match="no state token"):
        parse(a_tracker(body=body))


def test_a_state_outside_the_closed_set_is_refused_by_name() -> None:
    body = an_entry(state="NEARLY", check="exists pyproject.toml")
    with pytest.raises(TrackerDefectError, match="unknown state 'NEARLY'"):
        parse(a_tracker(body=body))


def test_the_state_of_every_entry_in_the_real_file_is_one_of_the_four(
    tracker_text: str,
) -> None:
    for entry in entries_of(tracker_text):
        assert entry.state in STATES, f"{entry.identifier} carries state {entry.state!r}"


def test_an_unverifiable_admission_with_no_reason_is_refused() -> None:
    body = an_entry(check=UNVERIFIABLE)
    with pytest.raises(TrackerDefectError, match="with no reason"):
        parse(a_tracker(body=body))


def test_an_unverifiable_admission_too_short_to_act_on_is_refused() -> None:
    """`UNVERIFIABLE too hard` is the shape this refuses."""
    body = an_entry(check=f"{UNVERIFIABLE} " + " ".join(["word"] * (FEWEST_WORDS_IN_A_REASON - 1)))
    with pytest.raises(TrackerDefectError, match="reason is too short"):
        parse(a_tracker(body=body))


def test_a_check_block_before_the_first_entry_is_refused() -> None:
    with pytest.raises(TrackerDefectError, match="belongs to no entry"):
        parse("# Title\n\n```check\nexists pyproject.toml\n```\n\n" + WELL_FORMED[10:])


def test_a_self_count_that_disagrees_with_the_file_is_caught() -> None:
    wrong = WELL_FORMED.replace("entries=1", "entries=99")
    assert declared_totals(wrong) != counted_totals(entries_of(wrong))


def test_a_missing_self_count_is_refused() -> None:
    without = re.sub(r"```totals\n.*?\n```\n", "", WELL_FORMED, flags=re.DOTALL)
    with pytest.raises(TrackerDefectError, match="exactly one line in one"):
        declared_totals(without)


def test_a_malformed_self_count_is_refused() -> None:
    with pytest.raises(TrackerDefectError, match="must read"):
        declared_totals(WELL_FORMED.replace("entries=1 predicates=1 unverifiable=0", "lots"))


# ═══════════════════════════════════════════════════════════════════════════
# THE VOCABULARY ITSELF — each verb decides both ways, and neither vacuously
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    ("check", "expected"),
    [
        (Check(1, "exists", ("present.py",)), True),
        (Check(1, "exists", ("gone.py",)), False),
        (Check(1, "absent", ("gone.py",)), True),
        (Check(1, "absent", ("present.py",)), False),
        (Check(1, "defines", ("present.py", "wanted")), True),
        (Check(1, "defines", ("present.py", "missing")), False),
        (Check(1, "not-defines", ("present.py", "missing")), True),
        (Check(1, "not-defines", ("present.py", "wanted")), False),
        (Check(1, "contains", ("present.py", "wanted")), True),
        (Check(1, "contains", ("present.py", "nowhere")), False),
        (Check(1, "not-contains", ("present.py", "nowhere")), True),
        (Check(1, "not-contains", ("present.py", "wanted")), False),
    ],
)
def test_each_verb_decides_both_ways(check: Check, expected: bool, tmp_path: Path) -> None:
    (tmp_path / "present.py").write_text("def wanted() -> None: ...\n", encoding="utf-8")
    held, _ = verify_tracker._evaluate(check, tmp_path)
    assert held is expected


@pytest.mark.parametrize("verb", ["not-defines", "not-contains", "contains", "defines"])
def test_a_content_verb_over_a_missing_file_is_false_and_never_vacuously_true(
    verb: str, tmp_path: Path
) -> None:
    """The hole a typo would otherwise open.

    `not-defines typo.py Anything` is true of every file that does not exist,
    so a mistyped path would satisfy an entry while checking nothing. The
    negative verbs are the dangerous half; the positive ones are here so the
    parametrisation states the rule for the whole class.
    """
    held, detail = verify_tracker._evaluate(Check(1, verb, ("typo.py", "X")), tmp_path)
    assert held is False
    assert "is not a file" in detail


def test_defines_reads_module_scope_and_not_a_name_bound_inside_a_function(
    tmp_path: Path,
) -> None:
    """`defines` must mean importable, not merely mentioned.

    F-024 was exactly this distinction: `Exclusion` appeared in a docstring, an
    enum's reasons and a test's import, and was defined nowhere an importer
    could reach.
    """
    (tmp_path / "m.py").write_text(
        "def outer() -> None:\n    Hidden = 1\n    return Hidden\n", encoding="utf-8"
    )
    held, _ = verify_tracker._evaluate(Check(1, "defines", ("m.py", "Hidden")), tmp_path)
    assert held is False


def test_defines_over_a_file_that_is_not_python_is_refused(tmp_path: Path) -> None:
    (tmp_path / "notes.md").write_text("Exclusion\n", encoding="utf-8")
    with pytest.raises(TrackerDefectError, match="needs a Python file"):
        verify_tracker._evaluate(Check(1, "defines", ("notes.md", "Exclusion")), tmp_path)


def test_the_verb_table_and_the_parser_agree_on_the_whole_vocabulary() -> None:
    """One source of truth for the vocabulary (Law 19)."""
    for verb, arity in ARITY.items():
        body = an_entry(check=" ".join([verb, *"ab"[:arity]]))
        entry = entries_of(a_tracker(body=body))[0]
        assert entry.checks[0].verb == verb
    assert CHECK_LANGUAGE == "check"


def test_a_check_renders_back_to_the_line_it_was_written_as() -> None:
    """The failure message quotes the predicate; it must quote it verbatim."""
    assert str(Check(1, "contains", ("a.py", "text"))) == "contains a.py text"


def test_a_blank_line_inside_a_check_block_is_refused() -> None:
    body = an_entry(check="exists pyproject.toml\n\nexists pyproject.toml")
    with pytest.raises(TrackerDefectError, match="blank line inside a check block"):
        parse(a_tracker(body=body))


def test_an_empty_check_block_is_refused() -> None:
    """A block with a fence and nothing between it declares no predicate."""
    body = "## F-001 · A title\n\n| **Status** | `OPEN` · ⬜ new |\n\n```check\n```\n"
    with pytest.raises(TrackerDefectError, match="check block is empty"):
        parse(a_tracker(body=body))


def test_a_file_with_no_entries_parses_to_nothing_rather_than_crashing() -> None:
    """And the scale guard, not the parser, is what calls that wrong.

    Separated deliberately: a parser that raised here could not be pointed at a
    fragment, and a parser that silently returned nothing would be the failure
    `test_the_tracker_parses_and_describes_the_file_it_claims_to` exists to
    catch. One does the reading, the other does the judging.
    """
    assert entries_of("# KNOWN_FAILURES.md\n\nprose, no headings\n") == ()
    assert FEWEST_ENTRIES_THAT_CAN_BE_REAL > 0


def test_a_declared_section_may_not_carry_a_check_block() -> None:
    """Only entries make claims; a section with a predicate has no owner."""
    body = WELL_FORMED[WELL_FORMED.index("## F-001") :] + (
        "\n## Closed\n\n```check\nexists pyproject.toml\n```\n"
    )
    with pytest.raises(TrackerDefectError, match="a declared section carries"):
        parse(a_tracker(body=body))


# ═══════════════════════════════════════════════════════════════════════════
# THE COMMAND LINE — what CI would actually invoke
# ═══════════════════════════════════════════════════════════════════════════


def a_tiny_repository(tmp_path: Path, *, check: str) -> Path:
    """A root holding nothing but a one-entry tracker."""
    (tmp_path / TRACKER).write_text(a_tracker(body=an_entry(check=check)), encoding="utf-8")
    return tmp_path


def test_the_command_line_reports_zero_and_names_every_entry(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    root = a_tiny_repository(tmp_path, check="absent nothing-is-here")
    assert verify_tracker.main([str(root)]) == 0
    printed = capsys.readouterr().out
    assert "TRUE          F-001" in printed
    assert "1 entries · 1 predicates · 0 carrying" in printed


def test_the_command_line_reports_non_zero_and_names_the_contradiction(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    """The exit code CI reads, and the line a human needs beside it."""
    root = a_tiny_repository(tmp_path, check="exists never-written.py")
    assert verify_tracker.main([str(root)]) == 1
    printed = capsys.readouterr().out
    assert "FALSE         F-001" in printed
    assert "1 contradicted" in printed
    assert "never-written.py is not there" in printed


def test_the_command_line_defaults_to_this_repository(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """No argument means the real tracker, which is how CI will call it."""
    assert verify_tracker.main([]) == 0
    assert str(FEWEST_ENTRIES_THAT_CAN_BE_REAL) not in capsys.readouterr().err


def test_running_the_module_as_a_script_exits_with_its_verdict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The `__main__` block is what CI executes, so it is what is tested.

    `running_path`, not `authored_path`: whatever is being executed must be
    what is being measured, which is the rule `authored_source` states for
    exactly this case.
    """
    monkeypatch.setattr(sys, "argv", ["verify_tracker.py"])
    with pytest.raises(SystemExit) as raised:
        runpy.run_path(str(running_path(verify_tracker)), run_name="__main__")
    assert raised.value.code == 0


def test_markup_quoted_inside_a_code_block_is_not_read_as_markup() -> None:
    """The file quotes headings and table rows inside fences throughout."""
    body = (
        "## F-002 · Quotes a heading\n\n| **Status** | `OPEN` · ⬜ real |\n\n"
        "```\n## F-999 · Not an entry\n| **Status** | `CLOSED` · invented |\n```\n\n"
        "```check\nexists pyproject.toml\n```\n"
    )
    identifiers = [entry.identifier for entry in entries_of(a_tracker(body=body))]
    assert identifiers == ["F-002"]
