# Tests for evaluation statistics, finding matching, and persistence.
# Fixtures use temporary SQLite files and deterministic metric inputs.

import sqlite3
from types import SimpleNamespace

import pytest

from evals.matching import findings_match, match_findings, unsafe_pass_summary
from evals.results import SuiteCaseResult, SuiteResult, git_code_version, save_suite_result
from evals.stats import paired_bootstrap_difference, proportion_summary, wilson_interval
from mergeguard.storage import connect


def test_wilson_interval_handles_zero_and_full_samples():
    """Return no interval without observations and bounded intervals otherwise."""
    assert wilson_interval(0, 0) is None
    lower, upper = wilson_interval(10, 10)
    assert 0 < lower < upper
    assert upper == pytest.approx(1)


def test_proportion_summary_suppresses_small_sample_percentage():
    """Keep raw counts without percentage claims below thirty cases."""
    assert proportion_summary(2, 10) == {
        "successes": 2,
        "total": 10,
        "rate": None,
        "wilson_95": None,
    }


def test_proportion_summary_reports_interval_at_thirty_cases():
    """Add a rate and Wilson interval at the reporting threshold."""
    summary = proportion_summary(15, 30)
    assert summary["rate"] == 0.5
    assert summary["wilson_95"] is not None


def test_wilson_interval_rejects_invalid_counts():
    """Reject a success count larger than its sample."""
    with pytest.raises(ValueError):
        wilson_interval(3, 2)


def test_paired_bootstrap_is_reproducible_and_measures_candidate_minus_baseline():
    """Use paired differences and a fixed seed for repeatable confidence bounds."""
    first = paired_bootstrap_difference([0, 1, 0], [1, 1, 1], iterations=200)
    second = paired_bootstrap_difference([0, 1, 0], [1, 1, 1], iterations=200)
    assert first == second
    assert first.difference == pytest.approx(2 / 3)
    assert first.lower <= first.difference <= first.upper


def test_paired_bootstrap_rejects_unpaired_samples():
    """Require equal non-empty sample lengths for paired comparisons."""
    with pytest.raises(ValueError):
        paired_bootstrap_difference([1], [1, 2])


def test_findings_match_applies_file_category_and_line_tolerance():
    """Match a nearby range only when both file and category agree."""
    expected = {"file": "app.py", "category": "sql_injection", "line_start": 10, "line_end": 12}
    predicted = {"file": "app.py", "category": "sql_injection", "line_start": 15, "line_end": 16}
    assert findings_match(expected, predicted)
    assert not findings_match(expected, {**predicted, "file": "other.py"})
    assert not findings_match(expected, {**predicted, "line_start": 16})


def test_match_findings_uses_one_to_one_maximum_matching():
    """Count each expected and predicted finding at most once."""
    expected = [
        {"file": "app.py", "category": "xss", "line_start": 10, "line_end": 10},
        {"file": "app.py", "category": "xss", "line_start": 13, "line_end": 13},
    ]
    predicted = [
        {"file": "app.py", "category": "xss", "line_start": 11, "line_end": 13},
        {"file": "app.py", "category": "xss", "line_start": 10, "line_end": 10},
        {"file": "app.py", "category": "xss", "line_start": 30, "line_end": 30},
    ]
    result = match_findings(expected, predicted)
    assert result.matched_count == 2
    assert result.recall is None
    assert result.precision is None


def test_match_findings_reports_rates_for_large_slices():
    """Report precision and recall only after the small-sample threshold."""
    expected = [
        {"file": "app.py", "category": "xss", "line_start": i * 10, "line_end": i * 10}
        for i in range(1, 31)
    ]
    predicted = expected[:25] + [
        {"file": "other.py", "category": "xss", "line_start": i, "line_end": i} for i in range(5)
    ]

    result = match_findings(expected, predicted)

    assert result.recall == pytest.approx(25 / 30)
    assert result.precision == pytest.approx(25 / 30)


def test_unsafe_pass_summary_uses_only_must_catch_cases():
    """Count passing outcomes only among cases labeled must-catch."""
    result = unsafe_pass_summary(
        [
            {"must_catch": True, "actual_outcome": "pass"},
            {"must_catch": True, "actual_outcome": "block"},
            {"must_catch": False, "actual_outcome": "pass"},
        ]
    )
    assert result["successes"] == 1
    assert result["total"] == 2
    assert result["rate"] is None


def test_git_code_version_reads_head_commit(monkeypatch, tmp_path):
    """Record the exact commit returned by Git."""
    monkeypatch.setattr(
        "evals.results.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(stdout="abc123\n"),
    )
    assert git_code_version(tmp_path) == "abc123"


def test_git_code_version_falls_back_outside_repository(monkeypatch, tmp_path):
    """Return a readable sentinel when Git is unavailable."""

    def fail(*args, **kwargs):
        raise FileNotFoundError("git")

    monkeypatch.setattr("evals.results.subprocess.run", fail)
    assert git_code_version(tmp_path) == "unknown"


def test_save_suite_result_persists_metadata_and_case_rows(tmp_path):
    """Store suite metadata and reconstructable case outcomes in SQLite."""
    connection = connect(tmp_path / "eval.db")
    try:
        result = SuiteResult(
            layer="L1",
            dataset_version="v0.1",
            repeats=1,
            metrics={"passed": 1},
            cases=(
                SuiteCaseResult(
                    "case-1",
                    1,
                    True,
                    {"decision": "block"},
                    {"decision": "block"},
                    run_id="trace-1",
                ),
            ),
            eval_run_id="eval-1",
            prompt_versions={"security": "v1"},
            model_config={"mode": "replay"},
        )

        saved = save_suite_result(result, code_version="abc123", connection=connection)
        run = connection.execute("SELECT * FROM eval_runs WHERE eval_run_id = 'eval-1'").fetchone()
        case = connection.execute(
            "SELECT * FROM eval_results WHERE eval_run_id = 'eval-1'"
        ).fetchone()

        assert saved["case_count"] == 1
        assert run["code_version"] == "abc123"
        assert run["dataset_version"] == "v0.1"
        assert case["passed"] == 1
        assert case["run_id"] == "trace-1"
    finally:
        connection.close()


def test_save_suite_result_rolls_back_when_case_insert_fails(tmp_path):
    """Avoid leaving a suite row behind when saving one of its cases fails."""
    connection = connect(tmp_path / "eval-rollback.db")
    try:
        connection.execute("""CREATE TRIGGER reject_eval_case BEFORE INSERT ON eval_results
            BEGIN SELECT RAISE(ABORT, 'test failure'); END""")
        result = SuiteResult(
            layer="L1",
            dataset_version="v0.1",
            repeats=1,
            metrics={},
            cases=(SuiteCaseResult("case-1", 1, True, {}, {}),),
            eval_run_id="eval-rollback",
        )

        with pytest.raises(sqlite3.IntegrityError):
            save_suite_result(result, code_version="abc123", connection=connection)
        count = connection.execute(
            "SELECT COUNT(*) FROM eval_runs WHERE eval_run_id = 'eval-rollback'"
        ).fetchone()[0]
        assert count == 0
    finally:
        connection.close()
