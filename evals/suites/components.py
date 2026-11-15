# Runs deterministic L1 component checks and combines their metrics.
# Every per-case outcome is returned in the shared persistence contract.

from __future__ import annotations

import tempfile
from dataclasses import replace
from pathlib import Path

from evals.config import EvalConfig
from evals.results import SuiteCaseResult, SuiteResult
from evals.suites.component_decisions import evaluate_risk_and_judge
from evals.suites.component_parsing import evaluate_diff_parser
from evals.suites.component_scanning import (
    evaluate_pattern_scanner,
    evaluate_redactor,
    evaluate_secret_scanner,
)
from evals.suites.component_verification import (
    evaluate_verifier,
    evaluate_webhook_signature,
)
from mergeguard.storage import connect


def run(config: EvalConfig) -> SuiteResult:
    """Run all model-free L1 components for the requested dataset slice."""
    metrics: dict[str, object] = {}
    cases: list[SuiteCaseResult] = []
    for repeat in range(1, config.repeats + 1):
        parser_accuracy, parser_cases = evaluate_diff_parser()
        secret_recall, secret_false_positive, secret_cases = evaluate_secret_scanner()
        pattern_by_category, pattern_cases = evaluate_pattern_scanner(
            config.dataset_version, config.split, config.cases
        )
        redactor_rate, redactor_cases = evaluate_redactor()
        fabricated_rate, genuine_rejection_rate, verifier_cases = evaluate_verifier(
            config.dataset_version, config.split, config.cases
        )
        risk_metrics, decision_cases = evaluate_risk_and_judge()
        webhook_rate, webhook_cases = _evaluate_webhook()
        metrics = {
            "diff_parser_line_accuracy": parser_accuracy,
            "secret_scanner_recall": secret_recall,
            "secret_scanner_false_positive_rate": secret_false_positive,
            "pattern_scanner_by_category": pattern_by_category,
            "redactor_removal_rate": redactor_rate,
            "verifier_fabricated_acceptance_rate": fabricated_rate,
            "verifier_genuine_rejection_rate": genuine_rejection_rate,
            **risk_metrics,
            "webhook_valid_first_acceptance_rate": webhook_rate,
        }
        repeated_cases = (
            parser_cases
            + secret_cases
            + pattern_cases
            + redactor_cases
            + verifier_cases
            + decision_cases
            + webhook_cases
        )
        cases.extend(replace(case, repeat=repeat) for case in repeated_cases)
    return SuiteResult(
        layer=config.layer,
        dataset_version=config.dataset_version,
        repeats=config.repeats,
        metrics=metrics,
        cases=tuple(cases),
        model_config={"mode": config.mode, "split": config.split},
    )


def _evaluate_webhook() -> tuple[float, list[SuiteCaseResult]]:
    """Test webhook signatures and replay protection using a disposable DB."""
    with tempfile.TemporaryDirectory(prefix="mergeguard-webhook-eval-") as directory:
        connection = connect(Path(directory) / "eval.db")
        try:
            return evaluate_webhook_signature(connection)
        finally:
            connection.close()
