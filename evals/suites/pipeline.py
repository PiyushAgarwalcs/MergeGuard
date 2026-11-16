# End-to-end evaluation of the graph on labeled development cases.
# With no credentials, reviewers use scripted empty replies while rule scanning remains real.

from __future__ import annotations

import asyncio
import hashlib
import time
from collections import Counter
from typing import Any

from langgraph.checkpoint.memory import InMemorySaver

from evals.config import EvalConfig
from evals.results import SuiteCaseResult, SuiteResult
from evals.suites.agent_security import _is_localized, _match_findings, _repo_root
from evals.suites.dataset_cases import load_cases
from mergeguard.checks.diff_parser import parse_diff
from mergeguard.graph import build_graph
from mergeguard.llm_fake import ScriptedLLM
from mergeguard.models import Decision, PullRequest
from mergeguard.settings import settings


def run(config: EvalConfig) -> SuiteResult:
    """Run the review graph and report L4 quality, safety, latency and stub cost."""
    cases = load_cases(config.dataset_version, config.split)
    cases = [(record, diff) for record, diff in cases if "findings" in record]
    if config.cases is not None:
        cases = cases[: config.cases]
    use_stub = not (settings.LLM_API_KEY and settings.LLM_BASE_URL)
    observations: list[dict[str, Any]] = []
    results: list[SuiteCaseResult] = []
    for repeat in range(1, config.repeats + 1):
        for record, diff in cases:
            started = time.perf_counter()
            actual = _review(record, diff)
            elapsed = time.perf_counter() - started
            predictions = actual["findings"]
            expected = record.get("findings", [])
            pairs = _match_findings(expected, predictions)
            localized = sum(_is_localized(label, item) for label, item in pairs)
            must_catch = bool(record.get("must_catch"))
            expected_decision = record.get("expected_decision", "pass")
            decision = actual["outcome"]
            unsafe_pass = must_catch and decision == "pass"
            over_block = not must_catch and decision == "block"
            over_escalation = not must_catch and decision == "needs_human"
            observations.append(
                {
                    "record": record,
                    "diff": diff,
                    "expected": expected,
                    "predictions": predictions,
                    "pairs": pairs,
                    "localized": localized,
                    "decision": decision,
                    "unsafe_pass": unsafe_pass,
                    "over_block": over_block,
                    "over_escalation": over_escalation,
                    "latency": elapsed,
                }
            )
            results.append(
                SuiteCaseResult(
                    case_id=f"pipeline-{record['id']}",
                    repeat=repeat,
                    passed=(not unsafe_pass and len(pairs) == len(expected)),
                    expected={"decision": expected_decision, "findings": expected},
                    actual={
                        "decision": decision,
                        "finding_count": len(predictions),
                        "complete": actual["complete"],
                    },
                    metrics={
                        "source": record.get("source"),
                        "category": record.get("category"),
                        "difficulty": record.get("difficulty"),
                        "diff_lines": len(diff.splitlines()),
                        "latency_seconds": elapsed,
                        "mode": "stub" if use_stub else config.mode,
                    },
                    run_id=f"pipeline-{record['id']}-r{repeat}",
                )
            )
    expected_count = sum(len(item["expected"]) for item in observations)
    prediction_count = sum(len(item["predictions"]) for item in observations)
    match_count = sum(len(item["pairs"]) for item in observations)
    localized_count = sum(item["localized"] for item in observations)
    severity_matches = sum(
        finding.severity.value == label["severity"]
        for item in observations
        for label, finding in item["pairs"]
    )
    must_catch_count = sum(bool(item["record"].get("must_catch")) for item in observations)
    clean_count = len(observations) - must_catch_count
    slices: dict[str, Any] = {}
    for key in ("source", "category", "difficulty", "diff_size"):
        grouped: dict[str, list[dict[str, Any]]] = {}
        for item in observations:
            if key == "diff_size":
                line_count = len(item["diff"].splitlines())
                label = "small" if line_count < 100 else "medium" if line_count < 500 else "large"
            else:
                label = str(item["record"].get(key, "unknown"))
            grouped.setdefault(label, []).append(item)
        slices[key] = {
            label: {
                "cases": len(group),
                "unsafe_pass": sum(x["unsafe_pass"] for x in group),
                "finding_recall": _ratio(
                    sum(len(x["pairs"]) for x in group), sum(len(x["expected"]) for x in group)
                ),
            }
            for label, group in sorted(grouped.items())
        }
    latencies = sorted(item["latency"] for item in observations)
    metrics = {
        "reviewer_mode": "stub" if use_stub else config.mode,
        "confusion_matrix": _confusion(observations),
        "unsafe_pass_rate": _ratio(sum(x["unsafe_pass"] for x in observations), must_catch_count),
        "over_block_rate": _ratio(sum(x["over_block"] for x in observations), clean_count),
        "over_escalation_rate": _ratio(
            sum(x["over_escalation"] for x in observations), clean_count
        ),
        "finding_recall": _ratio(match_count, expected_count),
        "precision": _ratio(localized_count, prediction_count),
        "localization_accuracy": _ratio(localized_count, match_count),
        "severity_agreement": _ratio(severity_matches, match_count),
        "p50_latency_seconds": _percentile(latencies, 0.50),
        "p95_latency_seconds": _percentile(latencies, 0.95),
        "cost_usd_per_pr": 0.0 if use_stub else None,
        "tokens_per_pr": 0 if use_stub else None,
        "slices": slices,
        "case_count": len(observations),
        "small_sample_note": "Slices below 30 cases show raw counts; percentages are descriptive.",
    }
    return SuiteResult(
        layer="pipeline",
        dataset_version=config.dataset_version,
        repeats=config.repeats,
        metrics=metrics,
        cases=tuple(results),
        prompt_versions={
            "graph": "phase-6",
            "security_reviewer": "security_reviewer.v1",
            "correctness_reviewer": "correctness_reviewer.v1",
            "test_reviewer": "test_reviewer.v1",
        },
        model_config={"mode": metrics["reviewer_mode"], "split": config.split, "variant": "full"},
    )


def _review(
    record: dict[str, Any],
    diff: str,
    variant: str = "full",
    *,
    use_stub: bool = True,
    mode: str = "replay",
) -> dict[str, Any]:
    files = sorted({hunk.file for hunk in parse_diff(diff)})
    digest = hashlib.sha256(diff.encode()).hexdigest()
    pr = PullRequest(
        repo="eval/sample",
        number=1,
        head_sha=digest,
        base_sha="dataset-base",
        title="Evaluation case",
        body="",
        author="dataset",
        diff=diff,
        files=files,
    )
    clients = (
        {
            name: ScriptedLLM([[]])
            for name in (
                "security_reviewer",
                "correctness_reviewer",
                "test_reviewer",
                "single_reviewer",
                "skeptic",
            )
        }
        if use_stub
        else None
    )
    graph = build_graph(
        checkpointer=InMemorySaver(),
        variant=variant,
        clients=clients,
    )
    previous_mode = settings.LLM_MODE
    settings.LLM_MODE = "record" if use_stub or mode == "live" else "replay"
    graph_config = {"configurable": {"thread_id": f"pipeline-{record['id']}"}}
    initial_state = {
        "pr": pr,
        "repo_path": str(_repo_root(files)),
        "run_id": f"pipeline-{record['id']}",
        "ci_status": "missing",
        "incomplete": False,
    }
    try:
        result = asyncio.run(_invoke_review(graph, initial_state, graph_config))
    finally:
        settings.LLM_MODE = previous_mode
    return {
        "outcome": result["decision"].outcome,
        "findings": result.get("decision_findings", []),
        "complete": result["decision"].complete,
    }


async def _invoke_review(
    graph: Any, state: dict[str, Any], config: dict[str, Any]
) -> dict[str, Any]:
    """Return a safe decision when the graph pauses at the human gate."""
    result = await graph.ainvoke(state, config=config)
    if "decision" in result:
        return result
    snapshot = await graph.aget_state(config)
    saved_state = {**state, **dict(snapshot.values)}
    if "decision" not in saved_state:
        pr = saved_state["pr"]
        saved_state["decision"] = Decision(
            outcome="needs_human",
            reasons=["Review paused before a decision was checkpointed."],
            head_sha=pr.head_sha,
            risk_score=0,
            complete=False,
        )
    saved_state.setdefault("decision_findings", saved_state.get("verified_findings", []))
    return saved_state


def _confusion(observations: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    matrix: dict[str, Counter[str]] = {}
    for item in observations:
        label = "must_catch" if item["record"].get("must_catch") else "clean"
        matrix.setdefault(label, Counter())[item["decision"]] += 1
    return {label: dict(counts) for label, counts in matrix.items()}


def _ratio(value: int, total: int) -> float:
    return value / total if total else 0.0


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    return values[min(len(values) - 1, int((len(values) - 1) * percentile))]
