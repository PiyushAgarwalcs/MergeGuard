# Marks judge-derived evaluation scores as unvalidated.
# Mechanical checks and seeded ground truth remain the source of acceptance gates.

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any


def mark_judge_metrics_unvalidated(metrics: Mapping[str, Any]) -> dict[str, Any]:
    """Keep judge-derived scores visible while marking them as unvalidated."""
    annotated = {key: _mark_value(key, value) for key, value in metrics.items()}
    annotated["judge_metric_validation"] = "not_validated"
    return annotated


def _mark_value(key: str, value: Any) -> Any:
    """Label numeric values whose metric name identifies them as judge-derived."""
    if isinstance(value, dict):
        return {name: _mark_value(name, item) for name, item in value.items()}
    if "judge" in key.casefold() and _numeric(value):
        return {"value": value, "validation": "not_validated"}
    return value


def _numeric(value: Any) -> bool:
    """Check for a finite number without treating booleans as scores."""
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
