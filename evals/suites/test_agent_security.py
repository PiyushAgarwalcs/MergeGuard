# Tests the agent-security baseline path with credentials disabled.
# The rule scanner provides deterministic findings and never contacts a model.

from __future__ import annotations

from evals.config import EvalConfig
from evals.suites.agent_security import run
from mergeguard.settings import settings


def test_security_suite_uses_labeled_stub_without_credentials(monkeypatch) -> None:
    """Run a stable dev slice and label its scanner-backed reviewer as stub."""
    monkeypatch.setattr(settings, "LLM_API_KEY", "")
    monkeypatch.setattr(settings, "LLM_BASE_URL", "")
    result = run(EvalConfig(layer="agent_security", split="dev", cases=35, mode="replay"))

    assert result.layer == "agent_security"
    assert result.model_config == {"mode": "stub", "split": "dev"}
    assert result.metrics["reviewer_mode"] == "stub"
    assert len(result.cases) == 35
    assert all(
        case.metrics["source"] in {"seeded", "hard_negative", "presumed_clean"}
        for case in result.cases
    )
    assert result.metrics["complete_rate"] == 1.0
    assert result.metrics["quote_validity"] == 1.0
    assert "command_injection" in result.metrics["recall_by_category"]
