# Tests critical regression failures, interval-based quality gates and warnings.
# Minimal result records exercise exactly the saved baseline/candidate contract.

from __future__ import annotations

from evals.config import EvalConfig
from evals.gates import evaluate_regression, run_gate_self_test
from evals.suites.regression import run


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
