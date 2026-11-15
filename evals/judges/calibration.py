# Loads human judge-calibration samples and calculates agreement statistics.
# Metrics remain explicitly uncalibrated until forty complete samples exist.

from __future__ import annotations

import json
import math
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

CALIBRATION_SAMPLE_TARGET = 40
CALIBRATION_PATH = Path(__file__).with_name("calibration.jsonl")


@dataclass(frozen=True)
class CalibrationSample:
    """One complete paired human and judge rating record."""

    sample_id: str
    case_id: str
    human_score: float
    judge_score: float
    judge_model: str
    rubric_version: str


def cohen_kappa(human: Sequence[str], judge: Sequence[str]) -> float | None:
    """Calculate Cohen's kappa for two equal-length categorical rating lists."""
    if len(human) != len(judge):
        raise ValueError("Rater lists must have the same length.")
    if not human:
        return None
    total = len(human)
    observed = sum(left == right for left, right in zip(human, judge, strict=True)) / total
    human_counts, judge_counts = Counter(human), Counter(judge)
    expected = (
        sum(
            human_counts[key] * judge_counts[key]
            for key in human_counts.keys() | judge_counts.keys()
        )
        / total**2
    )
    if expected == 1.0:
        return 1.0 if observed == 1.0 else 0.0
    return (observed - expected) / (1 - expected)


def spearman_rank(human: Sequence[float], judge: Sequence[float]) -> float | None:
    """Calculate Spearman's rank correlation, assigning average ranks to ties."""
    if len(human) != len(judge):
        raise ValueError("Rater lists must have the same length.")
    if len(human) < 2:
        return None
    return _pearson(_average_ranks(human), _average_ranks(judge))


def load_calibration_samples(path: Path = CALIBRATION_PATH) -> list[CalibrationSample]:
    """Load complete JSONL calibration rows and ignore the empty template row."""
    if not path.is_file():
        return []
    samples = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as error:
            raise ValueError(f"Invalid calibration JSON on line {line_number}.") from error
        if not isinstance(row, dict):
            raise TypeError(f"Calibration line {line_number} must contain a JSON object.")
        if row.get("human_score") is None or row.get("judge_score") is None:
            continue
        samples.append(_sample_from_row(row))
    return samples


def annotate_judge_metrics(metrics: Mapping[str, Any], sample_count: int) -> dict[str, Any]:
    """Add calibration state beside every judge-derived metric and at the root."""
    status = "calibrated" if sample_count >= CALIBRATION_SAMPLE_TARGET else "uncalibrated"
    annotated = {key: _annotate_value(key, value, status) for key, value in metrics.items()}
    annotated["judge_calibration"] = {
        "status": status,
        "sample_count": sample_count,
        "required_samples": CALIBRATION_SAMPLE_TARGET,
    }
    return annotated


def _sample_from_row(row: dict[str, Any]) -> CalibrationSample:
    """Validate the required fields of a complete calibration row."""
    required = ("sample_id", "case_id", "judge_model", "rubric_version")
    if any(not isinstance(row.get(key), str) or not row[key].strip() for key in required):
        raise ValueError("Complete calibration rows require sample, case, model and rubric IDs.")
    scores = (row["human_score"], row["judge_score"])
    if any(not _numeric(value) or not 1 <= value <= 5 for value in scores):
        raise ValueError("Calibration scores must be finite numbers from 1 through 5.")
    return CalibrationSample(
        sample_id=row["sample_id"],
        case_id=row["case_id"],
        human_score=float(scores[0]),
        judge_score=float(scores[1]),
        judge_model=row["judge_model"],
        rubric_version=row["rubric_version"],
    )


def _annotate_value(key: str, value: Any, status: str) -> Any:
    """Recursively add a status field alongside a judge-based numeric metric."""
    if isinstance(value, dict):
        annotated = {name: _annotate_value(name, item, status) for name, item in value.items()}
        if "judge" in key.casefold() and _numeric(value):
            annotated[f"{key}_calibration"] = status
        return annotated
    if "judge" in key.casefold() and _numeric(value):
        return {"value": value, "calibration": status}
    return value


def _average_ranks(values: Sequence[float]) -> list[float]:
    """Assign one-based average ranks to ties while preserving input order."""
    order = sorted(range(len(values)), key=lambda index: values[index])
    ranks = [0.0] * len(values)
    start = 0
    while start < len(order):
        end = start + 1
        while end < len(order) and values[order[end]] == values[order[start]]:
            end += 1
        average = (start + 1 + end) / 2
        for offset in range(start, end):
            ranks[order[offset]] = average
        start = end
    return ranks


def _pearson(left: Sequence[float], right: Sequence[float]) -> float | None:
    """Return Pearson correlation or None when either rank vector is constant."""
    left_mean, right_mean = sum(left) / len(left), sum(right) / len(right)
    covariance = sum((a - left_mean) * (b - right_mean) for a, b in zip(left, right, strict=True))
    left_variance = sum((value - left_mean) ** 2 for value in left)
    right_variance = sum((value - right_mean) ** 2 for value in right)
    denominator = math.sqrt(left_variance * right_variance)
    return covariance / denominator if denominator else None


def _numeric(value: Any) -> bool:
    """Check that a metric is finite and numeric, excluding booleans."""
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
