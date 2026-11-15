# Tests critical regression failures, interval-based quality gates and warnings.
# Minimal result records exercise exactly the saved baseline/candidate contract.

from __future__ import annotations

import json

from evals.config import EvalConfig
from evals.gate_cli import saved_regression_report
from evals.gates import GateReport, evaluate_regression, run_gate_self_test
from evals.results import SuiteCaseResult, SuiteResult, save_suite_result
from evals.suites.regression import run
from mergeguard.storage import connect


def _record(metric: str, value: float, outcome: str = "needs_human") -> dict:
    return {
        "summary": {metric: value, "unsafe_pass_rate": 0.0},
        "results": [
            {"case_id": f"case-{index}", "repeat": 1, "metrics": {metric: value}}
            for index in range(2)
        ],
    }


def test_gate_self_test_passes_baseline_and_fails_degraded_candidate() -> None:
    baseline, degraded = run_gate_self_test()

    assert baseline.passed
    assert not degraded.passed
    assert any("finding_recall" in failure for failure in degraded.failures)


def test_gate_fails_on_unsafe_canary_pass() -> None:
    record = _record("finding_recall", 0.9)
    record["results"][0].update(expected={"must_catch": True}, actual={"outcome": "pass"})

    result = evaluate_regression({"pipeline": record}, {"pipeline": record})

    assert not result.passed
    assert any("must-catch" in failure for failure in result.failures)


def test_gate_fails_on_recall_interval_beyond_limit() -> None:
    baseline = {"pipeline": _record("finding_recall", 0.9)}
    candidate = {"pipeline": _record("finding_recall", 0.8)}

    result = evaluate_regression(baseline, candidate)

    assert not result.passed
    assert any("beyond" in failure for failure in result.failures)


def test_gate_fails_on_false_positive_interval_beyond_limit() -> None:
    baseline = {"agent": _record("false_positive_rate", 0.1)}
    candidate = {"agent": _record("false_positive_rate", 0.2)}

    result = evaluate_regression(baseline, candidate)

    assert not result.passed
    assert any("false_positive_rate" in failure for failure in result.failures)


def test_gate_warns_on_cost_increase_without_failing() -> None:
    baseline = {"pipeline": {"summary": {"cost_usd_per_pr": 1.0}, "results": []}}
    candidate = {"pipeline": {"summary": {"cost_usd_per_pr": 1.3}, "results": []}}

    result = evaluate_regression(baseline, candidate)

    assert result.passed
    assert any("cost_usd_per_pr" in warning for warning in result.warnings)


def test_regression_suite_records_gate_self_test() -> None:
    result = run(EvalConfig(layer="regression"))

    assert result.metrics["gate_self_test"] == 1.0
    assert all(case.passed for case in result.cases)


def test_saved_gate_compares_latest_layer_run_with_committed_baseline(tmp_path) -> None:
    database = connect(tmp_path / "saved-gate.db")
    baseline_result = SuiteResult(
        layer="pipeline",
        dataset_version="v0.1",
        repeats=1,
        metrics={"finding_recall": 0.9, "unsafe_pass_rate": 0.0},
        cases=(SuiteCaseResult("case-1", 1, True, {}, {}, {"finding_recall": 0.9}),),
        eval_run_id="saved-baseline",
    )
    candidate_result = SuiteResult(
        layer="pipeline",
        dataset_version="v0.1",
        repeats=1,
        metrics={"finding_recall": 0.9, "unsafe_pass_rate": 0.0},
        cases=(SuiteCaseResult("case-1", 1, True, {}, {}, {"finding_recall": 0.9}),),
        eval_run_id="saved-candidate",
    )
    save_suite_result(baseline_result, connection=database)
    save_suite_result(candidate_result, connection=database)
    baseline_path = tmp_path / "main.json"
    baseline_path.write_text(
        json.dumps(
            {
                "layers": {
                    "pipeline": {
                        "eval_run_id": "saved-baseline",
                        "summary": baseline_result.metrics,
                        "results": [
                            {
                                "case_id": "case-1",
                                "repeat": 1,
                                "metrics": {"finding_recall": 0.9},
                            }
                        ],
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    report = saved_regression_report(baseline_path, connection=database)

    assert report.passed
    assert report.failures == ()
    database.close()


def test_gate_cli_prints_report_and_returns_its_status(monkeypatch, capsys) -> None:
    from evals import run as eval_runner

    monkeypatch.setattr(
        eval_runner,
        "saved_regression_report",
        lambda: GateReport(False, ("pipeline: test regression",), ("latency increased",)),
    )

    status = eval_runner.main(["gate"])

    assert status == 1
    assert '"passed": false' in capsys.readouterr().out
