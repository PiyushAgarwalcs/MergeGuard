# Matches reported findings to construction-labeled expectations.
# A maximum one-to-one match avoids counting one report more than once.

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from evals.stats import proportion_summary


@dataclass(frozen=True)
class MatchSummary:
    """One-to-one finding matches and their recall and precision metrics."""

    pairs: tuple[tuple[int, int], ...]
    expected_count: int
    predicted_count: int
    matched_count: int
    recall: float | None
    precision: float | None


def findings_match(
    expected: Mapping[str, Any], predicted: Mapping[str, Any], tolerance: int = 3
) -> bool:
    """Check file, category and line-range proximity for one finding pair."""
    if tolerance < 0:
        raise ValueError("Line tolerance cannot be negative.")
    return (
        expected.get("file") == predicted.get("file")
        and expected.get("category") == predicted.get("category")
        and int(predicted.get("line_start", 0)) <= int(expected.get("line_end", 0)) + tolerance
        and int(predicted.get("line_end", 0)) >= int(expected.get("line_start", 0)) - tolerance
    )


def match_findings(
    expected: Sequence[Mapping[str, Any]],
    predicted: Sequence[Mapping[str, Any]],
    tolerance: int = 3,
) -> MatchSummary:
    """Find the maximum one-to-one matching and calculate raw precision/recall."""
    matched_expected: dict[int, int] = {}

    def assign(predicted_index: int, visited: set[int]) -> bool:
        for expected_index, item in enumerate(expected):
            if expected_index in visited or not findings_match(
                item, predicted[predicted_index], tolerance
            ):
                continue
            visited.add(expected_index)
            if expected_index not in matched_expected or assign(
                matched_expected[expected_index], visited
            ):
                matched_expected[expected_index] = predicted_index
                return True
        return False

    for predicted_index in range(len(predicted)):
        assign(predicted_index, set())
    count = len(matched_expected)
    recall = proportion_summary(count, len(expected))["rate"]
    precision = proportion_summary(count, len(predicted))["rate"]
    pairs = tuple(
        sorted(
            (expected_index, pred_index) for expected_index, pred_index in matched_expected.items()
        )
    )
    return MatchSummary(pairs, len(expected), len(predicted), count, recall, precision)


def unsafe_pass_summary(cases: Sequence[Mapping[str, Any]]) -> dict[str, object]:
    """Summarize must-catch cases that were incorrectly passed."""
    must_catch = [case for case in cases if case.get("must_catch")]
    unsafe_passes = sum(case.get("actual_outcome") == "pass" for case in must_catch)
    return proportion_summary(unsafe_passes, len(must_catch))
