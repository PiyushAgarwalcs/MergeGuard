# Statistical helpers for evaluation results.
# Small samples keep raw counts and suppress percentage claims.

from __future__ import annotations

import random
from collections.abc import Sequence
from dataclasses import dataclass
from math import sqrt

MIN_PERCENTAGE_SAMPLE = 30
BOOTSTRAP_RESAMPLES = 1000
BOOTSTRAP_SEED = 42
WILSON_Z_95 = 1.959963984540054


@dataclass(frozen=True)
class BootstrapInterval:
    """Observed paired difference and percentile confidence bounds."""

    difference: float
    lower: float
    upper: float


def wilson_interval(
    successes: int, total: int, z: float = WILSON_Z_95
) -> tuple[float, float] | None:
    """Return a Wilson score interval for a proportion, or None with no data."""
    _validate_counts(successes, total)
    if total == 0:
        return None
    proportion = successes / total
    denominator = 1 + z * z / total
    center = (proportion + z * z / (2 * total)) / denominator
    margin = z * sqrt(proportion * (1 - proportion) / total + z * z / (4 * total**2))
    return max(0.0, center - margin / denominator), min(1.0, center + margin / denominator)


def proportion_summary(successes: int, total: int) -> dict[str, object]:
    """Return counts for all samples and rates only when at least 30 exist."""
    _validate_counts(successes, total)
    if total < MIN_PERCENTAGE_SAMPLE:
        return {"successes": successes, "total": total, "rate": None, "wilson_95": None}
    return {
        "successes": successes,
        "total": total,
        "rate": successes / total,
        "wilson_95": wilson_interval(successes, total),
    }


def paired_bootstrap_difference(
    baseline: Sequence[float],
    candidate: Sequence[float],
    *,
    iterations: int = BOOTSTRAP_RESAMPLES,
    seed: int = BOOTSTRAP_SEED,
    confidence: float = 0.95,
) -> BootstrapInterval:
    """Estimate candidate minus baseline with a deterministic paired bootstrap."""
    if not baseline or len(baseline) != len(candidate):
        raise ValueError("Paired samples must be non-empty and have equal lengths.")
    if iterations < 1 or not 0 < confidence < 1:
        raise ValueError("Iterations must be positive and confidence must be between 0 and 1.")
    differences = [new - old for old, new in zip(baseline, candidate, strict=True)]
    rng = random.Random(seed)
    estimates = [
        sum(rng.choice(differences) for _ in differences) / len(differences)
        for _ in range(iterations)
    ]
    estimates.sort()
    tail = (1 - confidence) / 2
    lower_index = int(tail * (iterations - 1))
    upper_index = int((1 - tail) * (iterations - 1))
    return BootstrapInterval(
        sum(differences) / len(differences), estimates[lower_index], estimates[upper_index]
    )


def _validate_counts(successes: int, total: int) -> None:
    """Reject impossible count inputs before producing a metric."""
    if total < 0 or successes < 0 or successes > total:
        raise ValueError("Counts must satisfy 0 <= successes <= total.")
