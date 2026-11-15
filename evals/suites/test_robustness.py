# Tests the L5 fake-model robustness suite and its explicit live skip labeling.
# The fake cases exercise the production graph without contacting external models.

from evals.config import EvalConfig
from evals.results import SuiteCaseResult
from evals.suites import robustness
from evals.suites.robustness import run
from mergeguard.settings import settings


def test_robustness_suite_preserves_injection_decisions_and_handles_odd_inputs() -> None:
    result = run(EvalConfig(layer="robustness", cases=4))

    assert result.metrics["mode"] == "fake"
    assert result.metrics["injection_case_count"] == 4
    assert result.metrics["injection_decision_changes"] == 0
    assert result.metrics["attacker_marker_leaks"] == 0
    assert result.metrics["odd_input_crashes"] == 0
    assert all(case.passed for case in result.cases)


def test_live_robustness_without_credentials_is_labeled_and_uses_fake(
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "LLM_API_KEY", "")
    monkeypatch.setattr(settings, "LLM_BASE_URL", "")

    result = run(EvalConfig(layer="robustness", mode="live", cases=0))

    assert result.metrics["mode"] == "fake"
    assert result.metrics["live_skipped_no_credentials"] == 1.0
    assert result.model_config["skip_reason"] == "missing LLM credentials"


def test_live_robustness_honors_repeat_count_when_credentials_exist(monkeypatch) -> None:
    monkeypatch.setattr(settings, "LLM_API_KEY", "fixture-key")
    monkeypatch.setattr(settings, "LLM_BASE_URL", "https://models.invalid/v1")
    monkeypatch.setattr(
        robustness,
        "_injection_results",
        lambda config, scripted, repeat: (
            SuiteCaseResult(
                "injection-fixture",
                repeat,
                True,
                {},
                {},
                {"no_marker_leak": True},
            ),
        ),
    )
    monkeypatch.setattr(robustness, "_odd_input_results", lambda scripted, repeat: ())

    result = run(EvalConfig(layer="robustness", mode="live", repeats=3))

    assert result.repeats == 3
    assert [case.repeat for case in result.cases] == [1, 2, 3]
