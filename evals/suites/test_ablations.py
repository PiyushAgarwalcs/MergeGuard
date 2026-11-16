# Tests for paired graph ablation execution and persisted case metrics.

from evals.config import EvalConfig
from evals.suites import ablations
from mergeguard.settings import settings


def test_ablation_suite_pairs_variants_and_writes_report(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(settings, "LLM_API_KEY", "")
    monkeypatch.setattr(settings, "LLM_BASE_URL", "")
    report = tmp_path / "evaluation.md"
    monkeypatch.setattr(ablations, "REPORT_PATH", report)

    result = ablations.run(EvalConfig(layer="ablations", split="dev", cases=2, mode="replay"))

    assert result.metrics["reviewer_mode"] == "stub"
    assert set(result.metrics["variants"]) == set(ablations.VARIANTS)
    assert set(result.metrics["paired_differences_vs_full"]) == set(ablations.VARIANTS) - {"full"}
    assert report.is_file()
    assert "single agent" in report.read_text(encoding="utf-8")
    assert "CI is missing" in report.read_text(encoding="utf-8")
    assert len(result.cases) == 2 * len(ablations.VARIANTS)
    assert all(item["incomplete_cases"] == 0 for item in result.metrics["variants"].values())
