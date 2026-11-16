# Tests for threshold parsing, gate evaluation, and registered suite execution.
# The runner uses an in-memory SQLite connection to avoid touching user data.

import json

import pytest

from evals.config import EvalConfig
from evals.results import SuiteCaseResult, SuiteResult
from evals.run import (
    check_thresholds,
    execute_evaluation,
    load_thresholds,
    main,
)
from mergeguard.storage import connect


def test_threshold_file_contains_component_bars_and_starting_targets():
    """Load every configured component bar and starting metric target."""
    thresholds = load_thresholds()
    assert "components" in thresholds["suites"]
    assert "unsafe_pass_rate_canary" in thresholds["targets"]


def test_load_thresholds_rejects_invalid_top_level(tmp_path):
    """Require a suites mapping in the YAML file."""
    path = tmp_path / "thresholds.yml"
    path.write_text("version: 1\n", encoding="utf-8")
    with pytest.raises(TypeError):
        load_thresholds(path)


def test_check_thresholds_passes_minimum_and_maximum_bars():
    """Compare actual metrics against configured lower and upper bounds."""
    result = check_thresholds(
        {"recall": 0.95, "false_positive_rate": 0.01},
        {"recall": {"min": 0.9}, "false_positive_rate": {"max": 0.02}},
    )
    assert result.passed
    assert all(bar["passed"] for bar in result.bars)


def test_check_thresholds_fails_missing_and_below_bar_metrics():
    """Fail a suite if any configured metric is missing or below its bar."""
    result = check_thresholds(
        {"recall": 0.8},
        {"recall": {"min": 0.9}, "precision": {"min": 0.95}},
    )
    assert not result.passed
    assert [bar["passed"] for bar in result.bars] == [False, False]


def test_check_thresholds_rejects_unknown_operators():
    """Reject misspelled comparison operators instead of silently passing."""
    with pytest.raises(ValueError):
        check_thresholds({"metric": 1}, {"metric": {"equal": 1}})


def test_execute_evaluation_runs_checks_bars_and_persists_results(tmp_path):
    """Run one suite and save the threshold outcome and case rows."""
    connection = connect(tmp_path / "runner.db")
    result = SuiteResult(
        layer="components",
        dataset_version="v0.1",
        repeats=1,
        metrics={"accuracy": 1.0, "judge_clarity": 0.8},
        cases=(SuiteCaseResult("case-1", 1, True, {"x": 1}, {"x": 1}, {"judge_accuracy": 0.6}),),
        eval_run_id="runner-1",
    )
    threshold_path = tmp_path / "thresholds.yml"
    threshold_path.write_text(
        "suites:\n  components:\n    accuracy:\n      min: 1.0\n", encoding="utf-8"
    )

    try:
        execution = execute_evaluation(
            EvalConfig("components"),
            thresholds_path=threshold_path,
            runner=lambda config: result,
            connection=connection,
        )
        saved = connection.execute(
            "SELECT summary FROM eval_runs WHERE eval_run_id = 'runner-1'"
        ).fetchone()
        saved_case = connection.execute(
            "SELECT metrics FROM eval_results WHERE eval_run_id = 'runner-1'"
        ).fetchone()
        assert execution.passed
        assert execution.case_count == 1
        summary = json.loads(saved["summary"])
        assert summary["thresholds_passed"] is True
        assert summary["judge_clarity"] == {"value": 0.8, "validation": "not_validated"}
        assert summary["judge_metric_validation"] == "not_validated"
        assert json.loads(saved_case["metrics"])["judge_accuracy"] == {
            "value": 0.6,
            "validation": "not_validated",
        }
    finally:
        connection.close()


def test_execute_evaluation_fails_when_metric_is_below_bar(tmp_path):
    """Return a failed execution when any suite threshold is missed."""
    connection = connect(tmp_path / "runner-fail.db")
    result = SuiteResult("components", "v0.1", 1, {"accuracy": 0.5}, (), eval_run_id="runner-fail")
    threshold_path = tmp_path / "thresholds.yml"
    threshold_path.write_text(
        "suites:\n  components:\n    accuracy:\n      min: 1.0\n", encoding="utf-8"
    )
    try:
        execution = execute_evaluation(
            EvalConfig("components"),
            thresholds_path=threshold_path,
            runner=lambda config: result,
            connection=connection,
        )
        assert not execution.passed
        assert execution.bars[0]["passed"] is False
    finally:
        connection.close()


def test_execute_evaluation_rejects_unregistered_suite():
    """Return a clear error when no suite has registered for a layer."""
    with pytest.raises(ValueError, match="No suite is registered"):
        execute_evaluation(EvalConfig("missing-suite"))


def test_main_returns_nonzero_when_suite_is_not_registered(capsys):
    """Expose missing suite registration as a failed CLI invocation."""
    status = main(["--layer", "missing-suite"])
    assert status == 1
    assert "No suite is registered" in capsys.readouterr().err
