# Repeats the production pipeline to measure decision and finding stability.
# Flaky case IDs are retained so unstable behavior can be reviewed directly.

from __future__ import annotations

from collections import Counter
from dataclasses import replace
from itertools import combinations
from typing import Any

from evals.config import EvalConfig
from evals.results import SuiteCaseResult, SuiteResult
from evals.suites.dataset_cases import load_cases
from evals.suites.pipeline import _review
from mergeguard.settings import settings

MINIMUM_REPEATS = 5
DECISION_AGREEMENT_BAR = 0.95


def run(config: EvalConfig) -> SuiteResult:
    """Run each selected case at least five times and summarize stability."""
    split = config.split or "test"
    cases = [
        (record, diff)
        for record, diff in load_cases(config.dataset_version, split)
        if "findings" in record
    ]
    if config.cases is not None:
        cases = cases[: config.cases]
    if not cases:
        raise ValueError(f"No consistency cases are available in the {split!r} split.")
    repeat_count = max(MINIMUM_REPEATS, config.repeats)
    use_stub = not (settings.LLM_API_KEY and settings.LLM_BASE_URL)
    observations: dict[str, list[dict[str, Any]]] = {}
    case_results: list[SuiteCaseResult] = []
    for record, diff in cases:
        case_id = str(record["id"])
        observations[case_id] = []
        for repeat in range(1, repeat_count + 1):
            actual = _review(record, diff, use_stub=use_stub, mode=config.mode)
            item = {"outcome": actual["outcome"], "findings": _finding_keys(actual["findings"])}
            observations[case_id].append(item)
            expected = record.get("expected_decision", "needs_human")
            case_results.append(
                SuiteCaseResult(
                    case_id=case_id,
                    repeat=repeat,
                    passed=actual["outcome"] != "pass" or not record.get("must_catch"),
                    expected={"decision": expected},
                    actual=item,
                    metrics={"mode": "stub" if use_stub else config.mode},
                    run_id=f"consistency-{case_id}-r{repeat}",
                )
            )
    agreements = {case_id: _decision_agreement(items) for case_id, items in observations.items()}
    jaccards = {case_id: _finding_jaccard(items) for case_id, items in observations.items()}
    flaky = sorted(
        case_id for case_id in observations if agreements[case_id] < DECISION_AGREEMENT_BAR
    )
    case_results = [
        replace(
            item,
            metrics={
                **item.metrics,
                "decision_agreement": agreements[item.case_id],
                "finding_jaccard": jaccards[item.case_id],
                "flaky": item.case_id in flaky,
            },
        )
        for item in case_results
    ]
    metrics: dict[str, Any] = {
        "mode": "stub" if use_stub else config.mode,
        "decision_agreement": sum(agreements.values()) / len(agreements),
        "finding_jaccard": sum(jaccards.values()) / len(jaccards),
        "flip_rate": len(flaky) / len(observations),
        "flaky_case_ids": flaky,
        "case_count": len(observations),
        "repeats_per_case": repeat_count,
    }
    if config.mode == "live" and use_stub:
        metrics["live_skipped_no_credentials"] = 1.0
    return SuiteResult(
        layer="consistency",
        dataset_version=config.dataset_version,
        repeats=repeat_count,
        metrics=metrics,
        cases=tuple(case_results),
        model_config={"mode": metrics["mode"], "split": split},
    )


def _finding_keys(findings: list[Any]) -> list[tuple[str, str, int, int]]:
    """Normalize findings into stable identities independent of generated IDs."""
    return sorted((item.category, item.file, item.line_start, item.line_end) for item in findings)


def _decision_agreement(observations: list[dict[str, Any]]) -> float:
    """Return the fraction of repeats sharing the modal decision."""
    counts = Counter(item["outcome"] for item in observations)
    return max(counts.values()) / len(observations)


def _finding_jaccard(observations: list[dict[str, Any]]) -> float:
    """Average pairwise Jaccard similarity of findings across repeats."""
    sets = [{tuple(item) for item in observation["findings"]} for observation in observations]
    similarities = []
    for left, right in combinations(sets, 2):
        union = left | right
        similarities.append(len(left & right) / len(union) if union else 1.0)
    return sum(similarities) / len(similarities) if similarities else 1.0
