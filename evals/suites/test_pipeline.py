# Tests for full-pipeline evaluation metrics, slices, and persisted outcomes.

from evals.config import EvalConfig
from evals.suites.pipeline import run
from mergeguard.settings import settings


def test_pipeline_suite_runs_graph_and_reports_l4_metrics(monkeypatch) -> None:
    monkeypatch.setattr(settings, "LLM_API_KEY", "")
    monkeypatch.setattr(settings, "LLM_BASE_URL", "")
    result = run(EvalConfig(layer="pipeline", split="dev", cases=4, mode="replay"))

    assert result.layer == "pipeline"
    assert result.metrics["reviewer_mode"] == "stub"
    assert result.metrics["case_count"] == 4
    assert "unsafe_pass_rate" in result.metrics
    assert "confusion_matrix" in result.metrics
    assert "difficulty" in result.metrics["slices"]
    assert all(case.actual["complete"] for case in result.cases)
