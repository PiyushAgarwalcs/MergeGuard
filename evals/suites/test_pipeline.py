# Tests full-pipeline evaluation and graph pauses for human review.
# Interrupted reviews use their safe decision from the saved checkpoint.

from types import SimpleNamespace
from typing import Any

from evals.config import EvalConfig
from evals.suites import pipeline
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


def test_review_reads_checkpoint_state_when_graph_interrupts(monkeypatch) -> None:
    class InterruptedGraph:
        async def ainvoke(self, *_args: Any, **_kwargs: Any) -> dict[str, Any]:
            self.state = _args[0]
            return {"__interrupt__": []}

        async def aget_state(self, _config: dict[str, Any]) -> SimpleNamespace:
            return SimpleNamespace(values=self.state)

    monkeypatch.setattr(pipeline, "build_graph", lambda **_kwargs: InterruptedGraph())

    result = pipeline._review(
        {"id": "case-interrupted"},
        "diff --git a/app.py b/app.py\n--- a/app.py\n+++ b/app.py\n@@ -1 +1 @@\n-old\n+new\n",
    )

    assert result == {"outcome": "needs_human", "findings": [], "complete": False}
