# Tests five-repeat consistency measurement and persisted flaky-case labels.
# A small test-split sample keeps this suite deterministic and fast in CI.

from evals.config import EvalConfig
from evals.suites.consistency import run


def test_consistency_suite_repeats_cases_and_records_agreement() -> None:
    result = run(EvalConfig(layer="consistency", cases=2, repeats=1))

    assert result.repeats == 5
    assert result.metrics["repeats_per_case"] == 5
    assert result.metrics["decision_agreement"] == 1.0
    assert result.metrics["flip_rate"] == 0.0
    assert len(result.cases) == 10
    assert all(case.metrics["flaky"] is False for case in result.cases)
    assert all(case.metrics["finding_jaccard"] == 1.0 for case in result.cases)
