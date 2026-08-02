"""Re-runs mean a name can have several check runs. Picking the wrong one hides a failure."""

from poll_checks import latest_per_name


def test_picks_the_newest_run_for_a_name() -> None:
    runs = [
        {"id": 1, "name": "lint", "conclusion": "failure"},
        {"id": 9, "name": "lint", "conclusion": "success"},
    ]
    assert latest_per_name(runs)["lint"]["conclusion"] == "success"


def test_a_stale_success_never_masks_a_newer_failure() -> None:
    # The dangerous direction: an old green run must not win over a new red one.
    runs = [
        {"id": 9, "name": "lint", "conclusion": "success"},
        {"id": 10, "name": "lint", "conclusion": "failure"},
    ]
    assert latest_per_name(runs)["lint"]["conclusion"] == "failure"


def test_order_of_the_input_does_not_matter() -> None:
    ascending = [
        {"id": 1, "name": "a", "conclusion": "x"},
        {"id": 2, "name": "a", "conclusion": "y"},
    ]
    assert latest_per_name(ascending) == latest_per_name(list(reversed(ascending)))


def test_separate_names_are_kept_separate() -> None:
    runs = [
        {"id": 1, "name": "lint", "conclusion": "success"},
        {"id": 2, "name": "build", "conclusion": "failure"},
    ]
    result = latest_per_name(runs)
    assert result["lint"]["conclusion"] == "success"
    assert result["build"]["conclusion"] == "failure"


def test_runs_without_a_name_are_ignored_not_crashed_on() -> None:
    runs = [{"id": 1, "conclusion": "success"}, {"id": 2, "name": "lint", "conclusion": "success"}]
    assert set(latest_per_name(runs)) == {"lint"}


def test_empty_input_gives_empty_output() -> None:
    assert latest_per_name([]) == {}
