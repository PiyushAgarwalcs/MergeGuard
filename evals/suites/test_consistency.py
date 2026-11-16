# Tests five-repeat consistency measurement and persisted flaky-case labels.
# A small test-split sample keeps this suite deterministic and fast in CI.

from evals.config import EvalConfig
from evals.suites import consistency
from mergeguard.settings import settings

run = consistency.run


def test_consistency_suite_repeats_cases_and_records_agreement() -> None:
    result = run(EvalConfig(layer="consistency", cases=2, repeats=1))

    assert result.repeats == 5
    assert result.metrics["repeats_per_case"] == 5
    assert result.metrics["decision_agreement"] == 1.0
    assert result.metrics["flip_rate"] == 0.0
    assert len(result.cases) == 10
    assert all(case.metrics["flaky"] is False for case in result.cases)
    assert all(case.metrics["finding_jaccard"] == 1.0 for case in result.cases)


def test_consistency_uses_ollama_without_an_api_key(monkeypatch) -> None:
    stub_values: list[bool] = []

    def fake_review(record, diff, *, use_stub=True, mode="replay"):
        del record, diff, mode
        stub_values.append(use_stub)
        return {"outcome": "needs_human", "findings": []}

    monkeypatch.setattr(settings, "LLM_PROVIDER", "ollama")
    monkeypatch.setattr(settings, "LLM_BASE_URL", "http://localhost:11434/v1")
    monkeypatch.setattr(settings, "LLM_API_KEY", "")
    monkeypatch.setattr(consistency, "_review", fake_review)

    result = run(EvalConfig(layer="consistency", split="test", cases=1, mode="live"))

    assert stub_values == [False] * 5
    assert result.metrics["mode"] == "live"
    assert "live_skipped_no_credentials" not in result.metrics


def test_consistency_quick_sample_spans_the_split() -> None:
    items = list(range(144))

    assert consistency._evenly_spaced_sample(items, 4) == [0, 48, 95, 143]
    assert consistency._evenly_spaced_sample(items, 1) == [72]
    assert consistency._evenly_spaced_sample(items, 144) == items
