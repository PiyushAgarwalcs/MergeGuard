# Proves that regression thresholds accept a baseline and reject a degraded stub.
# The self-test remains credential-free and deterministic for every commit.

from __future__ import annotations

from evals.config import EvalConfig
from evals.gates import run_gate_self_test
from evals.results import SuiteCaseResult, SuiteResult


def run(config: EvalConfig) -> SuiteResult:
    """Run the passing-baseline and deliberately-worsened self-test cases."""
    del config
    baseline, degraded = run_gate_self_test()
    outcomes = {
        "baseline_passes": baseline.passed,
        "worsened_candidate_fails": not degraded.passed,
    }
    cases = tuple(
        SuiteCaseResult(
            case_id=name,
            repeat=1,
            passed=passed,
            expected={"gate_result": True},
            actual={"gate_result": passed},
            metrics={"failures": len(degraded.failures)},
        )
        for name, passed in outcomes.items()
    )
    return SuiteResult(
        layer="regression",
        dataset_version="gate-self-test-v1",
        repeats=1,
        metrics={
            **{name: float(value) for name, value in outcomes.items()},
            "gate_self_test": float(all(outcomes.values())),
        },
        cases=cases,
        model_config={"mode": "deterministic_stub"},
    )
