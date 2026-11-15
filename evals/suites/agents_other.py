# Deterministic contract evaluations for the non-security agents.
# Scripted replies exercise schemas and safeguards without requiring credentials.

from __future__ import annotations

from evals.config import EvalConfig
from evals.results import SuiteCaseResult, SuiteResult
from mergeguard.agents import correctness_reviewer, reporter, test_reviewer
from mergeguard.agents import skeptic as skeptic_agent
from mergeguard.llm_fake import ScriptedLLM
from mergeguard.models import (
    Decision,
    Finding,
    Hunk,
    PullRequest,
    ReviewContext,
    ReviewState,
    Severity,
    SkepticVerdict,
    Source,
)
from mergeguard.settings import settings

DIFF = """--- a/src/example.py\n+++ b/src/example.py\n@@ -1 +1 @@\n+value = items[index]\n"""


def run(config: EvalConfig) -> SuiteResult:
    """Measure reviewer contracts, skeptic verdict handling and report faithfulness."""
    del config
    previous_mode = settings.LLM_MODE
    settings.LLM_MODE = "record"
    finding = Finding(
        id="F-1",
        source=Source.CORRECTNESS,
        category="off_by_one",
        severity=Severity.MEDIUM,
        file="src/example.py",
        line_start=1,
        line_end=1,
        quote="value = items[index]",
        explanation="The index may be outside the collection.",
        suggestion="Check the index before reading.",
    )
    pr = PullRequest(
        repo="eval/sample",
        number=1,
        head_sha="eval-sha",
        base_sha="base",
        title="contract case",
        body="",
        author="dataset",
        diff=DIFF,
        files=["src/example.py"],
    )
    state: ReviewState = {
        "pr": pr,
        "context": ReviewContext(ci_status="passing"),
        "run_id": "agents-other",
    }
    reply = [finding.model_dump(mode="json")]
    correctness = correctness_reviewer.run(state, client=ScriptedLLM([reply]))
    test_finding = finding.model_copy(update={"source": Source.TESTS, "category": "missing_test"})
    tests = test_reviewer.run(state, client=ScriptedLLM([[test_finding.model_dump(mode="json")]]))
    upheld = SkepticVerdict(finding_id="F-1", verdict="upheld", reason="The index is unchecked.")
    refuted = upheld.model_copy(update={"verdict": "refuted"})
    hunk = Hunk(file="src/example.py", new_start=1, new_end=1, text="+value = items[index]\n")
    retained = skeptic_agent.run(
        {"finding": finding, "hunk": hunk, "context": ReviewContext()},
        client=ScriptedLLM([upheld]),
    )
    dismissed = skeptic_agent.run(
        {"finding": finding, "hunk": hunk, "context": ReviewContext()},
        client=ScriptedLLM([refuted]),
    )
    decision = Decision(
        outcome="needs_human", reasons=["Review required."], head_sha="eval-sha", risk_score=10
    )
    faithful_report = reporter.render_comment([finding], decision)
    tampered_report = faithful_report.replace("src/example.py:L1", "src/fake.py:L1")
    format_retry = correctness_reviewer.run(state, client=ScriptedLLM(["not json", reply]))
    observations = {
        "correctness_complete": bool(correctness["complete"] and correctness["findings"]),
        "test_reviewer_complete": bool(tests["complete"] and tests["findings"]),
        "skeptic_true_retention": bool(
            retained["complete"] and retained["verdicts"][0].verdict == "upheld"
        ),
        "skeptic_false_refutation": bool(
            dismissed["complete"] and dismissed["verdicts"][0].verdict == "refuted"
        ),
        "reporter_faithful": reporter.is_faithful_comment(faithful_report, [finding]),
        "reporter_rejects_tampering": not reporter.is_faithful_comment(tampered_report, [finding]),
        "format_valid_after_retry": bool(format_retry["complete"] and format_retry["findings"]),
    }
    cases = tuple(
        SuiteCaseResult(
            case_id=name,
            repeat=1,
            passed=passed,
            expected={"passed": True},
            actual={"passed": passed},
            metrics={"mode": "stub"},
        )
        for name, passed in observations.items()
    )
    metrics = {name: float(value) for name, value in observations.items()}
    metrics["format_reliability"] = metrics.pop("format_valid_after_retry")
    result = SuiteResult(
        layer="agents_other",
        dataset_version="contracts-v1",
        repeats=1,
        metrics={**metrics, "reviewer_mode": "stub", "uncalibrated_clarity": True},
        cases=cases,
        prompt_versions={
            "correctness_reviewer": correctness_reviewer.PROMPT_NAME,
            "test_reviewer": test_reviewer.PROMPT_NAME,
            "skeptic": skeptic_agent.PROMPT_NAME,
            "reporter": reporter.PROMPT_NAME,
        },
        model_config={"mode": "stub", "split": "contract"},
    )
    settings.LLM_MODE = previous_mode
    return result
