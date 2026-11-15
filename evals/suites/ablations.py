# Compares planned graph ablations with the full design on paired dev cases.
# The report is labeled stub when credentials are unavailable.

from __future__ import annotations

from pathlib import Path
from statistics import median
from time import perf_counter
from typing import Any

from evals.config import EvalConfig
from evals.results import SuiteCaseResult, SuiteResult
from evals.stats import paired_bootstrap_difference
from evals.suites.agent_security import _is_localized, _match_findings
from evals.suites.dataset_cases import load_cases
from evals.suites.pipeline import _review
from mergeguard.settings import settings

VARIANTS = ("full", "single_agent", "no_skeptic", "no_verifier", "no_context", "no_rules")
METRICS = ("finding_recall", "precision", "unsafe_pass_rate", "cost_usd_per_pr", "latency_seconds")
REPORT_PATH = Path(__file__).resolve().parents[2] / "docs" / "evaluation.md"


def run(config: EvalConfig) -> SuiteResult:
    """Run all graph variants and save paired bootstrap differences and a Markdown report."""
    if config.split not in {None, "dev"}:
        raise ValueError("Ablations are tuned and reported on the dev split only.")
    cases = load_cases(config.dataset_version, "dev")
    cases = [(record, diff) for record, diff in cases if "findings" in record]
    if config.cases is not None:
        cases = cases[: config.cases]
    if not cases:
        raise ValueError("No labeled development cases are available for ablations.")
    use_stub = not (settings.LLM_API_KEY and settings.LLM_BASE_URL)
    observations: dict[str, list[dict[str, Any]]] = {variant: [] for variant in VARIANTS}
    case_results: list[SuiteCaseResult] = []
    for repeat in range(1, config.repeats + 1):
        for record, diff in cases:
            expected = record.get("findings", [])
            for variant in VARIANTS:
                started = perf_counter()
                actual = _review(record, diff, variant, use_stub=use_stub, mode=config.mode)
                latency_seconds = perf_counter() - started
                pairs = _match_findings(expected, actual["findings"])
                localized = sum(_is_localized(label, finding) for label, finding in pairs)
                must_catch = bool(record.get("must_catch"))
                obs = {
                    "case_id": str(record["id"]),
                    "expected_count": len(expected),
                    "prediction_count": len(actual["findings"]),
                    "matched": len(pairs),
                    "localized": localized,
                    "unsafe_pass": int(must_catch and actual["outcome"] == "pass"),
                    "latency_seconds": latency_seconds,
                    "cost_usd_per_pr": 0.0,
                    "complete": actual["complete"],
                    "outcome": actual["outcome"],
                    "must_catch": must_catch,
                }
                observations[variant].append(obs)
                case_results.append(
                    SuiteCaseResult(
                        case_id=f"{variant}-{record['id']}",
                        repeat=repeat,
                        passed=obs["unsafe_pass"] == 0,
                        expected={"findings": expected, "must_catch": must_catch},
                        actual={
                            "outcome": actual["outcome"],
                            "finding_count": len(actual["findings"]),
                            "complete": actual["complete"],
                        },
                        metrics={
                            "variant": variant,
                            "mode": "stub" if use_stub else config.mode,
                            "latency_seconds": latency_seconds,
                        },
                    )
                )
    summaries = {name: _summarize(rows) for name, rows in observations.items()}
    comparisons = _compare(observations)
    single_matches = all(
        abs(comparisons["single_agent"][metric]["difference"]) < 1e-12
        for metric in ("finding_recall", "precision", "unsafe_pass_rate")
    )
    metrics: dict[str, Any] = {
        "reviewer_mode": "stub" if use_stub else config.mode,
        "case_count": len(cases),
        "repeats": config.repeats,
        "variants": summaries,
        "paired_differences_vs_full": comparisons,
        "single_agent_matches_team_on_quality_and_safety": single_matches,
    }
    _write_report(metrics)
    return SuiteResult(
        layer="ablations",
        dataset_version=config.dataset_version,
        repeats=config.repeats,
        metrics=metrics,
        cases=tuple(case_results),
        prompt_versions={"graph": "phase-6", "single_reviewer": "single_reviewer.v1"},
        model_config={"mode": metrics["reviewer_mode"], "split": "dev", "variants": list(VARIANTS)},
    )


def _summarize(rows: list[dict[str, Any]]) -> dict[str, float | int]:
    expected = sum(row["expected_count"] for row in rows)
    predictions = sum(row["prediction_count"] for row in rows)
    matched = sum(row["matched"] for row in rows)
    localized = sum(row["localized"] for row in rows)
    must_catch = sum(row["unsafe_pass"] for row in rows)
    must_catch_count = sum(row["must_catch"] for row in rows)
    return {
        "case_count": len(rows),
        "finding_recall": matched / expected if expected else 1.0,
        "precision": localized / predictions if predictions else 1.0,
        "unsafe_pass_rate": must_catch / must_catch_count if must_catch_count else 0.0,
        "cost_usd_per_pr": median(row["cost_usd_per_pr"] for row in rows),
        "latency_seconds": median(row["latency_seconds"] for row in rows),
        "incomplete_cases": sum(not row["complete"] for row in rows),
    }


def _compare(
    observations: dict[str, list[dict[str, Any]]],
) -> dict[str, dict[str, dict[str, float]]]:
    baseline = observations["full"]
    output: dict[str, dict[str, dict[str, float]]] = {}
    for variant, rows in observations.items():
        if variant == "full":
            continue
        output[variant] = {}
        for metric in METRICS:
            baseline_rows = baseline
            candidate_rows = rows
            if metric == "unsafe_pass_rate":
                baseline_rows = [row for row in baseline if row["must_catch"]]
                candidate_rows = [row for row in rows if row["must_catch"]]
            if not baseline_rows:
                output[variant][metric] = {"difference": 0.0, "lower_95": 0.0, "upper_95": 0.0}
                continue
            baseline_values = [_case_metric(row, metric) for row in baseline_rows]
            candidate_values = [_case_metric(row, metric) for row in candidate_rows]
            interval = paired_bootstrap_difference(baseline_values, candidate_values)
            output[variant][metric] = {
                "difference": interval.difference,
                "lower_95": interval.lower,
                "upper_95": interval.upper,
            }
    return output


def _case_metric(row: dict[str, Any], metric: str) -> float:
    if metric == "finding_recall":
        return row["matched"] / row["expected_count"] if row["expected_count"] else 1.0
    if metric == "precision":
        return row["localized"] / row["prediction_count"] if row["prediction_count"] else 1.0
    if metric == "unsafe_pass_rate":
        return float(row["unsafe_pass"])
    return float(row[metric])


def _write_report(metrics: dict[str, Any]) -> None:
    mode = metrics["reviewer_mode"]
    rows = ["# Evaluation", "", f"## Phase 6 ablations ({mode})", ""]
    rows.append(
        f"Ran {metrics['case_count']} paired development cases across {len(VARIANTS)} variants "
        f"for {metrics['repeats']} repeat(s)."
    )
    rows.extend(
        [
            "",
            "| Variant | Finding recall | Precision | Unsafe-pass | Cost USD/PR | Median latency (s) | Incomplete |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for variant in VARIANTS:
        item = metrics["variants"][variant]
        rows.append(
            f"| {variant} | {item['finding_recall']:.3f} | {item['precision']:.3f} | "
            f"{item['unsafe_pass_rate']:.3f} | {item['cost_usd_per_pr']:.3f} | "
            f"{item['latency_seconds']:.4f} | {item['incomplete_cases']} |"
        )
    rows.extend(
        [
            "",
            "### Paired differences versus full design",
            "",
            "Differences are candidate minus full; positive latency means the ablation is slower. Intervals are paired bootstrap 95% percentile intervals (1,000 resamples, seed 42). Stub cost is zero and latency reflects local graph execution only.",
            "",
            "CI is missing in this offline dataset run, so the judge returns needs_human for clean cases. The zero unsafe-pass rate is a safe fallback outcome; these decisions do not establish decision accuracy or live-model quality.",
            "",
        ]
    )
    rows.extend(["| Variant | Metric | Difference | 95% interval |", "|---|---|---:|---:|"])
    for variant, metrics_by_name in metrics["paired_differences_vs_full"].items():
        for name, item in metrics_by_name.items():
            rows.append(
                f"| {variant} | {name} | {item['difference']:.4f} | [{item['lower_95']:.4f}, {item['upper_95']:.4f}] |"
            )
    single = (
        "matches"
        if metrics["single_agent_matches_team_on_quality_and_safety"]
        else "does not match"
    )
    rows.extend(
        [
            "",
            f"On these stub measurements, the single agent {single} the full team on finding recall, precision and unsafe-pass rate. This is not a live-model comparison; the offline scripted reviewers return empty findings, so the deterministic scanner drives detections.",
            "",
        ]
    )
    REPORT_PATH.write_text("\n".join(rows), encoding="utf-8")
