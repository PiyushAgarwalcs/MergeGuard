# Applies regression thresholds to saved baseline and candidate summaries.
# Critical safety failures block immediately; noisy quality changes use intervals.

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from evals.stats import paired_bootstrap_difference

RECALL_DROP_LIMIT = -0.03
FALSE_POSITIVE_RISE_LIMIT = 0.02
DECISION_AGREEMENT_DROP_LIMIT = -0.03
SCHEMA_VALID_MINIMUM = 0.99
WARNING_INCREASE_LIMIT = 0.20


@dataclass(frozen=True)
class GateReport:
    """Regression gate result with actionable failures and non-blocking warnings."""

    passed: bool
    failures: tuple[str, ...]
    warnings: tuple[str, ...]


def evaluate_regression(baseline: dict[str, Any], candidate: dict[str, Any]) -> GateReport:
    """Compare saved layer records and fail on safety or significant quality regressions."""
    failures: list[str] = []
    warnings: list[str] = []
    for layer, current in candidate.items():
        previous = baseline.get(layer)
        if previous is None:
            warnings.append(f"{layer}: no baseline exists; comparison skipped.")
            continue
        old_metrics = previous.get("summary", {})
        new_metrics = current.get("summary", {})
        failures.extend(_safety_failures(layer, current, new_metrics))
        _compare_quality_metrics(
            layer, previous, current, old_metrics, new_metrics, failures, warnings
        )
        failures.extend(_missed_bars(layer, new_metrics))
    return GateReport(not failures, tuple(failures), tuple(warnings))


def run_gate_self_test() -> tuple[GateReport, GateReport]:
    """Prove an unchanged baseline passes and a worsened recall fails the gate."""
    cases = [
        {"case_id": "one", "repeat": 1, "metrics": {"finding_recall": 0.9}},
        {"case_id": "two", "repeat": 1, "metrics": {"finding_recall": 0.9}},
    ]
    baseline = {
        "pipeline": {
            "summary": {"finding_recall": 0.9, "unsafe_pass_rate": 0.0},
            "results": cases,
        }
    }
    degraded = {
        "pipeline": {
            "summary": {"finding_recall": 0.7, "unsafe_pass_rate": 0.0},
            "results": [{**case, "metrics": {"finding_recall": 0.7}} for case in cases],
        }
    }
    return evaluate_regression(baseline, baseline), evaluate_regression(baseline, degraded)


def _safety_failures(layer: str, current: dict[str, Any], metrics: dict[str, Any]) -> list[str]:
    """Detect canary escapes, fabricated verifier acceptance, and invalid schemas."""
    failures = []
    unsafe = _metric(metrics, "unsafe_pass_rate_canary", "unsafe_pass_rate", "unsafe_pass_count")
    if unsafe is not None and unsafe > 0:
        failures.append(f"{layer}: unsafe pass metric is {unsafe:g}.")
    if _unsafe_canary_cases(current.get("results", [])):
        failures.append(f"{layer}: a must-catch case passed.")
    fabricated = _metric(
        metrics, "fabricated_findings_accepted", "verifier_fabricated_acceptance_rate"
    )
    if fabricated is not None and fabricated > 0:
        failures.append(f"{layer}: fabricated verifier acceptance is {fabricated:g}.")
    schema = _metric(metrics, "schema_valid_rate", "schema_valid_rate_after_retry")
    if schema is not None and schema < SCHEMA_VALID_MINIMUM:
        failures.append(f"{layer}: schema validity {schema:g} is below {SCHEMA_VALID_MINIMUM:.2f}.")
    return failures


def _compare_quality_metrics(
    layer: str,
    previous: dict[str, Any],
    current: dict[str, Any],
    old_metrics: dict[str, Any],
    new_metrics: dict[str, Any],
    failures: list[str],
    warnings: list[str],
) -> None:
    """Apply interval-based recall, false-positive and agreement rules."""
    checks = (
        (
            ("finding_recall", "security_recall", "seeded_security_recall_test"),
            RECALL_DROP_LIMIT,
            "below",
        ),
        (
            ("false_positive_rate", "hard_negative_false_positive_rate"),
            FALSE_POSITIVE_RISE_LIMIT,
            "above",
        ),
        (
            ("decision_agreement", "decision_agreement_five_repeats"),
            DECISION_AGREEMENT_DROP_LIMIT,
            "below",
        ),
    )
    for names, limit, direction in checks:
        name = next((key for key in names if key in old_metrics and key in new_metrics), None)
        if name is None:
            continue
        delta, interval = _paired_metric_delta(
            previous.get("results", []), current.get("results", []), name
        )
        if interval is None:
            warnings.append(
                f"{layer}: {name} has no paired case interval; observed delta {delta:+.3f}."
            )
            continue
        bound = interval[1] if direction == "below" else interval[0]
        regressed = bound < limit if direction == "below" else bound > limit
        if regressed:
            failures.append(f"{layer}: {name} delta {delta:+.3f} is beyond the {limit:+.2f} limit.")
    _increase_warning(layer, old_metrics, new_metrics, warnings)


def _paired_metric_delta(
    old_rows: list[dict[str, Any]], new_rows: list[dict[str, Any]], metric: str
) -> tuple[float, tuple[float, float] | None]:
    """Calculate a paired bootstrap interval when the same case metrics exist."""
    old = {_case_key(row): row.get("metrics", {}).get(metric) for row in old_rows}
    new = {_case_key(row): row.get("metrics", {}).get(metric) for row in new_rows}
    keys = sorted(old.keys() & new.keys())
    keys = [key for key in keys if _number(old[key]) and _number(new[key])]
    if not keys:
        return 0.0, None
    interval = paired_bootstrap_difference(
        [float(old[key]) for key in keys], [float(new[key]) for key in keys]
    )
    return interval.difference, (interval.lower, interval.upper)


def _increase_warning(
    layer: str, old: dict[str, Any], new: dict[str, Any], warnings: list[str]
) -> None:
    """Warn when latency or cost grows by more than the configured fraction."""
    for name in ("p95_latency_seconds", "latency_p95_seconds", "cost_usd_per_pr"):
        before, after = old.get(name), new.get(name)
        if (
            _number(before)
            and _number(after)
            and before > 0
            and after > before * (1 + WARNING_INCREASE_LIMIT)
        ):
            warnings.append(f"{layer}: {name} increased by more than {WARNING_INCREASE_LIMIT:.0%}.")


def _missed_bars(layer: str, metrics: dict[str, Any]) -> list[str]:
    """Fail when a component result records any missed L1 threshold bar."""
    if metrics.get("thresholds_passed") is False:
        return [f"{layer}: one or more suite threshold bars failed."]
    bars = metrics.get("threshold_bars", [])
    if isinstance(bars, list) and any(
        isinstance(bar, dict) and bar.get("passed") is False for bar in bars
    ):
        return [f"{layer}: one or more suite threshold bars failed."]
    return []


def _unsafe_canary_cases(rows: list[dict[str, Any]]) -> bool:
    """Find a must-catch case whose actual outcome passed."""
    return any(
        row.get("expected", {}).get("must_catch") and row.get("actual", {}).get("outcome") == "pass"
        for row in rows
    )


def _metric(metrics: dict[str, Any], *names: str) -> float | None:
    """Return the first supported finite scalar metric."""
    return next((float(metrics[name]) for name in names if _number(metrics.get(name))), None)


def _case_key(row: dict[str, Any]) -> tuple[str, int]:
    """Return the stable case and repeat identity."""
    return str(row.get("case_id", "")), int(row.get("repeat", 1))


def _number(value: Any) -> bool:
    """Accept finite numeric inputs and reject booleans and NaN."""
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )
