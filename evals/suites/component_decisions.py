# L1 risk-score properties, AUC and judge truth-table checks.
# Synthetic inputs keep all expected outcomes independent of model behavior.

from __future__ import annotations

from evals.results import SuiteCaseResult
from mergeguard.checks.judge import calculate_risk, judge_run
from mergeguard.models import Finding, PullRequest, ReviewContext, Severity, Source


def evaluate_risk_and_judge() -> tuple[dict[str, object], list[SuiteCaseResult]]:
    """Check risk monotonicity and the deterministic judge decision table."""
    results = _risk_property_cases()
    results.extend(_judge_cases())
    metrics = {
        "risk_auc": _risk_auc(),
        "critical_score_non_decrease": all(
            result.passed for result in results if result.metrics.get("property") == "critical"
        ),
        "risky_file_score_non_decrease": all(
            result.passed for result in results if result.metrics.get("property") == "risky_files"
        ),
        "judge_truth_table_accuracy": sum(
            result.passed for result in results if result.metrics.get("component") == "judge"
        )
        / len([result for result in results if result.metrics.get("component") == "judge"]),
    }
    return metrics, results


def _risk_property_cases() -> list[SuiteCaseResult]:
    """Verify adding critical findings or risk signals never lowers a score."""
    base = calculate_risk([], ["tests/test_safe.py"], "passing")
    critical = _finding(Severity.CRITICAL)
    after_critical = calculate_risk([critical], ["tests/test_safe.py"], "passing")
    files_base = calculate_risk([], ["app.py"], "passing")
    files_risky = calculate_risk([], ["app.py", "infra/policy.yml", "requirements.txt"], "failing")
    return [
        SuiteCaseResult(
            "l1-risk-critical-monotonicity",
            1,
            after_critical >= base,
            {"minimum_score": base},
            {"score": after_critical},
            {"property": "critical"},
        ),
        SuiteCaseResult(
            "l1-risk-more-signals-monotonicity",
            1,
            files_risky >= files_base,
            {"minimum_score": files_base},
            {"score": files_risky},
            {"property": "risky_files"},
        ),
    ]


def _risk_auc() -> float:
    """Calculate pairwise AUC for 30 safe and 30 risky deterministic inputs."""
    safe_scores = [calculate_risk([], ["tests/test_safe.py"], "passing") for _ in range(30)]
    risky_scores = [
        calculate_risk([_finding(Severity.HIGH)], ["src/service.py"], "passing") for _ in range(30)
    ]
    wins = sum(
        1.0 if risky > safe else 0.5 if risky == safe else 0.0
        for risky in risky_scores
        for safe in safe_scores
    )
    return wins / (len(risky_scores) * len(safe_scores))


def _judge_cases() -> list[SuiteCaseResult]:
    """Exercise each first-match branch and unknown-input fallback."""
    cases = [
        ("critical", [_finding(Severity.CRITICAL)], "passing", True, "block"),
        ("missing_diff", [], "passing", False, "needs_human"),
        ("ci_failing", [], "failing", True, "needs_human"),
        ("ci_missing", [], "missing", True, "needs_human"),
        ("high", [_finding(Severity.HIGH)], "passing", True, "needs_human"),
        (
            "risk_threshold",
            [_finding(Severity.MEDIUM, index) for index in range(1, 9)],
            "passing",
            True,
            "needs_human",
        ),
        ("low_risk", [_finding(Severity.LOW)], "passing", True, "pass"),
        ("missing_context", [], None, True, "needs_human"),
        ("clean", [], "passing", True, "pass"),
    ]
    results = []
    for case_id, findings, ci_status, has_diff, expected in cases:
        pr = _pull_request(has_diff)
        if case_id == "risk_threshold":
            pr = pr.model_copy(update={"files": ["src/auth/service.py", "requirements.txt"]})
            findings[0] = findings[0].model_copy(update={"line_end": 1100})
        state = {"pr": pr, "findings": findings}
        if ci_status is not None:
            state["context"] = ReviewContext(ci_status=ci_status)
        decision = judge_run(state)["decision"].outcome
        results.append(
            SuiteCaseResult(
                f"l1-judge-{case_id}",
                1,
                decision == expected,
                {"outcome": expected},
                {"outcome": decision},
                {"component": "judge"},
            )
        )
    return results


def _finding(severity: Severity, index: int = 1) -> Finding:
    """Create one schema-valid finding for risk and judge fixtures."""
    return Finding(
        id=f"L1-{index}",
        source=Source.RULE,
        category="wrong_condition",
        severity=severity,
        file="src/service.py",
        line_start=index,
        line_end=index,
        quote=f"value = {index}",
        explanation="Synthetic evaluation finding.",
        suggestion="Review the changed condition.",
    )


def _pull_request(has_diff: bool) -> PullRequest:
    """Create a stable local PR fixture with or without reviewable changes."""
    diff = (
        "diff --git a/src/service.py b/src/service.py\n" "@@ -1 +1 @@\n-value = 0\n+value = 1\n"
        if has_diff
        else ""
    )
    return PullRequest(
        repo="local/eval",
        number=1,
        head_sha="head",
        base_sha="base",
        title="L1 evaluation",
        body="",
        author="fixture",
        diff=diff,
        files=["src/service.py"],
    )
