# Tests rating agreement, placeholder filtering and uncalibrated metric labels.
# Calibration fixtures are synthetic and contain no human or model secrets.

from __future__ import annotations

import json
from pathlib import Path

import pytest

from evals.judges.calibration import (
    annotate_judge_metrics,
    cohen_kappa,
    load_calibration_samples,
    spearman_rank,
)


def test_cohen_kappa_handles_perfect_and_opposed_ratings() -> None:
    assert cohen_kappa(["low", "high", "low", "high"], ["low", "high", "low", "high"]) == 1.0
    assert cohen_kappa(["low", "high", "low", "high"], ["high", "low", "high", "low"]) == -1.0
    assert cohen_kappa([], []) is None


def test_spearman_rank_handles_order_and_ties() -> None:
    assert spearman_rank([1, 2, 3], [10, 20, 30]) == pytest.approx(1.0)
    assert spearman_rank([1, 2, 3], [30, 20, 10]) == pytest.approx(-1.0)
    assert spearman_rank([1, 1, 2], [2, 2, 3]) == pytest.approx(1.0)
    assert spearman_rank([1], [1]) is None


def test_calibration_loader_ignores_empty_template_and_reads_complete_rows(tmp_path: Path) -> None:
    path = tmp_path / "calibration.jsonl"
    placeholder = {
        "sample_id": None,
        "case_id": None,
        "human_score": None,
        "judge_score": None,
    }
    sample = {
        "sample_id": "S-1",
        "case_id": "case-1",
        "human_score": 4,
        "judge_score": 3,
        "judge_model": "judge-a",
        "rubric_version": "v1",
    }
    path.write_text(json.dumps(placeholder) + "\n" + json.dumps(sample) + "\n", encoding="utf-8")

    loaded = load_calibration_samples(path)

    assert len(loaded) == 1
    assert loaded[0].human_score == 4.0
    assert loaded[0].judge_score == 3.0


def test_judge_metrics_are_labeled_until_calibration_target_is_met() -> None:
    metrics = {"judge_clarity": 0.85, "finding_recall": 0.7}

    uncalibrated = annotate_judge_metrics(metrics, sample_count=39)
    calibrated = annotate_judge_metrics(metrics, sample_count=40)

    assert uncalibrated["judge_clarity"]["calibration"] == "uncalibrated"
    assert uncalibrated["judge_calibration"]["status"] == "uncalibrated"
    assert calibrated["judge_clarity"]["calibration"] == "calibrated"
    assert calibrated["finding_recall"] == 0.7
