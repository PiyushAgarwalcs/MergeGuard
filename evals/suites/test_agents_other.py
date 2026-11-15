from evals.config import EvalConfig
from evals.suites.agents_other import run


def test_other_agent_contract_suite_passes_with_scripted_stub() -> None:
    result = run(EvalConfig(layer="agents_other", split="dev"))

    assert result.metrics["reviewer_mode"] == "stub"
    assert result.metrics["format_reliability"] == 1.0
    assert result.metrics["skeptic_true_retention"] == 1.0
    assert all(case.passed for case in result.cases)
