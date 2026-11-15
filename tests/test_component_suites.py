# Tests for the deterministic L1 component suites.
# Expected metrics and labels come from fixtures, synthetic snippets and v0.1 cases.

from evals.config import EvalConfig
from evals.suites.component_decisions import evaluate_risk_and_judge
from evals.suites.component_parsing import evaluate_diff_parser
from evals.suites.component_scanning import (
    evaluate_pattern_scanner,
    evaluate_redactor,
    evaluate_secret_scanner,
)
from evals.suites.component_verification import evaluate_verifier, evaluate_webhook_signature
from evals.suites.components import run
from mergeguard.storage import connect


def test_diff_parser_component_suite_passes_all_fifty_cases():
    """Check 15 fixture diffs and 35 generated line-range cases."""
    accuracy, cases = evaluate_diff_parser()
    assert len(cases) == 50
    assert accuracy == 1.0


def test_secret_scanner_meets_recall_and_placeholder_bars():
    """Find all synthetic keys while leaving placeholders quiet."""
    recall, false_positive_rate, cases = evaluate_secret_scanner()
    assert len(cases) == 150
    assert recall >= 0.95
    assert false_positive_rate <= 0.02


def test_pattern_scanner_reports_seeded_results_by_category():
    """Report all security taxonomy categories with seeded counts."""
    metrics, cases = evaluate_pattern_scanner()
    assert len(cases) >= 48
    assert len(metrics) >= 12
    assert metrics["sql_injection"]["seeded_total"] == 4


def test_redactor_removes_all_one_hundred_fifty_synthetic_secrets():
    """Require every synthetic secret to disappear from redacted diff text."""
    removal_rate, cases = evaluate_redactor()
    assert len(cases) == 150
    assert removal_rate == 1.0


def test_verifier_rejects_all_attacks_and_accepts_genuine_findings():
    """Check fabricated evidence rejection and genuine finding retention."""
    attack_acceptance, genuine_rejection, cases = evaluate_verifier()
    assert len(cases) == 240
    assert attack_acceptance == 0.0
    assert genuine_rejection == 0.0


def test_risk_scorer_and_judge_meet_component_bars():
    """Check monotonic risk properties, synthetic AUC and judge truth table."""
    metrics, cases = evaluate_risk_and_judge()
    assert metrics["risk_auc"] == 1.0
    assert metrics["critical_score_non_decrease"]
    assert metrics["risky_file_score_non_decrease"]
    assert metrics["judge_truth_table_accuracy"] == 1.0
    assert all(case.passed for case in cases)


def test_webhook_component_rejects_invalid_and_replayed_deliveries(tmp_path):
    """Accept a signed delivery once and reject missing, bad and replayed input."""
    connection = connect(tmp_path / "webhook.db")
    try:
        accuracy, cases = evaluate_webhook_signature(connection)
    finally:
        connection.close()
    assert len(cases) == 5
    assert accuracy == 1.0


def test_component_runner_applies_the_requested_test_split():
    """Return repeat-tagged per-case results and all configured bar metrics."""
    result = run(EvalConfig("components", split="test", repeats=2))
    assert result.repeats == 2
    assert result.cases
    assert {case.repeat for case in result.cases} == {1, 2}
    assert result.metrics["judge_truth_table_accuracy"] == 1.0
    assert result.metrics["verifier_fabricated_acceptance_rate"] == 0.0
