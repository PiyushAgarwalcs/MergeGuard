# Evaluates the security reviewer by itself on labeled development cases.
# Model calls use replay/record modes; no-credential runs use the rule scanner.

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import Any

from evals.config import EvalConfig
from evals.results import SuiteCaseResult, SuiteResult
from evals.suites.dataset_cases import load_cases
from mergeguard.agents.security_reviewer import run as run_security_reviewer
from mergeguard.checks.collect_context import collect_context
from mergeguard.checks.diff_parser import parse_diff
from mergeguard.checks.rule_scan import scan_diff
from mergeguard.models import Finding, PullRequest, Source
from mergeguard.settings import settings

SAMPLE_REPOS = Path(__file__).resolve().parents[1] / "sample_repos"
SECURITY_CATEGORIES = {
    "hardcoded_secret",
    "sql_injection",
    "command_injection",
    "path_traversal",
    "unsafe_deserialization",
    "ssrf",
    "weak_crypto",
    "tls_verification_disabled",
    "xss",
    "missing_authorization",
    "insecure_randomness",
    "sensitive_data_in_logs",
}
EVALUATED_SOURCES = {"seeded", "hard_negative", "presumed_clean"}


def run(config: EvalConfig) -> SuiteResult:
    """Measure security findings on the selected development-split cases."""
    cases = [
        (record, diff)
        for record, diff in load_cases(config.dataset_version, config.split)
        if record["source"] in EVALUATED_SOURCES
    ]
    if config.cases is not None:
        cases = cases[: config.cases]
    use_stub = not (settings.LLM_API_KEY and settings.LLM_BASE_URL)
    previous_mode = settings.LLM_MODE
    if not use_stub:
        settings.LLM_MODE = "record" if config.mode == "live" else "replay"
    try:
        return _evaluate_cases(config, cases, use_stub)
    finally:
        settings.LLM_MODE = previous_mode


def _evaluate_cases(
    config: EvalConfig,
    cases: list[tuple[dict[str, Any], str]],
    use_stub: bool,
) -> SuiteResult:
    results: list[SuiteCaseResult] = []
    counts: Counter[str] = Counter()
    matches: Counter[str] = Counter()
    prediction_count = expected_count = localized = matched_count = quote_valid = severity_agree = 0
    hard_negative_total = hard_negative_false_positives = clean_total = clean_false_positives = 0
    complete_count = 0
    for repeat in range(1, config.repeats + 1):
        for record, diff in cases:
            expected = record.get("findings", [])
            predictions, complete = _review_case(record, diff, use_stub)
            complete_count += complete
            expected_count += len(expected)
            prediction_count += len(predictions)
            pairings = _match_findings(expected, predictions)
            localized += sum(_is_localized(label, finding) for label, finding in pairings)
            matched_count += len(pairings)
            quote_valid += sum(_quote_is_valid(finding.quote, diff) for finding in predictions)
            severity_agree += sum(
                finding.severity.value == label["severity"] for label, finding in pairings
            )
            for label in expected:
                counts[label["category"]] += 1
            for label, finding in pairings:
                if _is_localized(label, finding):
                    matches[label["category"]] += 1
            false_positive_count = len(predictions) - len(pairings)
            if record["source"] == "hard_negative":
                hard_negative_total += 1
                hard_negative_false_positives += bool(predictions)
            elif record["source"] == "presumed_clean":
                clean_total += 1
                clean_false_positives += bool(predictions)
            results.append(
                SuiteCaseResult(
                    f"security-{record['id']}",
                    repeat,
                    len(pairings) == len(expected) and false_positive_count == 0 and complete,
                    {"findings": expected},
                    {
                        "findings": [_finding_summary(item) for item in predictions],
                        "complete": complete,
                    },
                    {"source": record["source"], "mode": "stub" if use_stub else config.mode},
                    run_id=f"agent-security-{record['id']}-r{repeat}",
                )
            )
    category_recall = {
        category: matches[category] / count for category, count in sorted(counts.items())
    }
    return SuiteResult(
        layer="agent_security",
        dataset_version=config.dataset_version,
        repeats=config.repeats,
        metrics={
            "recall_by_category": category_recall,
            "reviewer_mode": "stub" if use_stub else config.mode,
            "precision": _ratio(localized, prediction_count),
            "localization_accuracy": _ratio(localized, matched_count),
            "quote_validity": _ratio(quote_valid, prediction_count),
            "severity_agreement": _ratio(severity_agree, matched_count),
            "hard_negative_false_positive_rate": _ratio(
                hard_negative_false_positives, hard_negative_total
            ),
            "presumed_clean_false_positive_rate": _ratio(clean_false_positives, clean_total),
            "complete_rate": _ratio(complete_count, len(results)),
            "expected_findings": expected_count,
            "predicted_findings": prediction_count,
        },
        cases=tuple(results),
        prompt_versions={"security_reviewer": "security_reviewer.v1"},
        model_config={"mode": "stub" if use_stub else config.mode, "split": config.split},
    )


def _review_case(record: dict[str, Any], diff: str, use_stub: bool) -> tuple[list[Finding], bool]:
    """Build fixed context, then call the agent or deterministic scanner stub."""
    files = sorted({hunk.file for hunk in parse_diff(diff)})
    repo_root = _repo_root(files)
    context = collect_context(repo_root, files, diff, "missing")
    if use_stub:
        findings = [
            item.model_copy(update={"source": Source.SECURITY})
            for item in scan_diff(diff)
            if item.category in SECURITY_CATEGORIES
        ]
        return findings, True
    pr = PullRequest(
        repo="eval/sample",
        number=1,
        head_sha=str(record["id"]),
        base_sha="dataset-base",
        title="Evaluation case",
        body="",
        author="dataset",
        diff=diff,
        files=files,
    )
    result = run_security_reviewer(
        {"pr": pr, "context": context, "run_id": f"agent-security-{record['id']}"}
    )
    return result["findings"], bool(result["complete"])


def _repo_root(files: list[str]) -> Path:
    """Map sample-app package paths to their committed source snapshots."""
    prefix = files[0].split("/", maxsplit=1)[0] if files else ""
    app_name = {
        "notes_api": "notes_api",
        "notes_tests": "notes_api",
        "shortener": "url_shortener",
        "shortener_tests": "url_shortener",
        "report_tool": "csv_report",
        "report_tests": "csv_report",
    }.get(prefix, "notes_api")
    return SAMPLE_REPOS / app_name


def _match_findings(
    expected: list[dict[str, Any]], predicted: list[Finding]
) -> list[tuple[dict[str, Any], Finding]]:
    """Match each labeled finding to one prediction of the same category."""
    remaining = list(predicted)
    pairs = []
    for label in expected:
        found = next(
            (item for item in remaining if item.category == label["category"]),
            None,
        )
        if found is not None:
            remaining.remove(found)
            pairs.append((label, found))
    return pairs


def _ranges_overlap(label: dict[str, Any], finding: Finding) -> bool:
    return not (finding.line_end < label["line_start"] or label["line_end"] < finding.line_start)


def _is_localized(label: dict[str, Any], finding: Finding) -> bool:
    return finding.file == label["file"] and _ranges_overlap(label, finding)


def _quote_is_valid(quote: str, diff: str) -> bool:
    def normalize(value: str) -> str:
        return re.sub(r"\s+", " ", value).strip()

    return bool(quote) and normalize(quote) in normalize(diff)


def _ratio(value: int, total: int) -> float:
    """Return a zero-safe fraction for an evaluation metric."""
    return value / total if total else 0.0


def _finding_summary(finding: Finding) -> dict[str, Any]:
    return {
        "category": finding.category,
        "severity": finding.severity.value,
        "file": finding.file,
        "line_start": finding.line_start,
        "line_end": finding.line_end,
        "quote": finding.quote,
    }
