# Tests for graph routing and safe integration outcomes under faults.

from evals.config import EvalConfig
from evals.suites.graph_integration import run


def test_graph_integration_suite_records_fail_closed_scenarios() -> None:
    result = run(EvalConfig(layer="integration"))

    assert result.metrics["reviewer_mode"] == "scripted"
    assert result.metrics["safe_route_rate"] == 1.0
    assert all(case.passed for case in result.cases)
    assert {case.case_id for case in result.cases} >= {
        "human_interrupt",
        "malformed_output_fails_closed",
        "model_timeout_fails_closed",
        "one_reviewer_failure_fails_closed",
    }
