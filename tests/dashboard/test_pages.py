# Smoke tests every dashboard page against populated and empty databases.
# Database selection uses an environment path resolved by the query layer.

import json
from pathlib import Path

from streamlit.testing.v1 import AppTest

from mergeguard.storage import connect, insert_eval_bundle
from tests.make_sample_db import build_sample_db

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PAGE_FILES = (
    REPOSITORY_ROOT / "dashboard" / "app.py",
    REPOSITORY_ROOT / "dashboard" / "pages" / "1_Overview.py",
    REPOSITORY_ROOT / "dashboard" / "pages" / "2_Layers.py",
    REPOSITORY_ROOT / "dashboard" / "pages" / "3_Pipeline.py",
    REPOSITORY_ROOT / "dashboard" / "pages" / "4_Case_Explorer.py",
    REPOSITORY_ROOT / "dashboard" / "pages" / "5_Compare_Runs.py",
    REPOSITORY_ROOT / "dashboard" / "pages" / "6_Consistency.py",
    REPOSITORY_ROOT / "dashboard" / "pages" / "7_Ablations.py",
    REPOSITORY_ROOT / "dashboard" / "pages" / "8_Cost_Latency.py",
    REPOSITORY_ROOT / "dashboard" / "pages" / "9_Dataset.py",
    REPOSITORY_ROOT / "dashboard" / "pages" / "10_Judge_Calibration.py",
)


def test_all_dashboard_pages_run_on_sample_database(tmp_path, monkeypatch):
    """Run every page with one saved evaluation result."""
    sample_path = build_sample_db(tmp_path / "sample.db")
    monkeypatch.setenv("DATABASE_PATH", str(sample_path))
    for page in PAGE_FILES:
        app = AppTest.from_file(str(page), default_timeout=30).run()
        assert not app.exception, f"{page.name}: {app.exception}"


def test_all_dashboard_pages_run_on_empty_database(tmp_path, monkeypatch):
    """Run every page when the SQLite schema exists but contains no rows."""
    empty_path = tmp_path / "empty.db"
    connection = connect(empty_path)
    connection.close()
    monkeypatch.setenv("DATABASE_PATH", str(empty_path))
    for page in PAGE_FILES:
        app = AppTest.from_file(str(page), default_timeout=30).run()
        assert not app.exception, f"{page.name}: {app.exception}"


def test_comparison_consistency_and_calibration_pages_show_saved_details(tmp_path, monkeypatch):
    sample_path = build_sample_db(tmp_path / "detailed.db")
    connection = connect(sample_path)
    try:
        for run_id, time, recall, outcome, passed in (
            ("pipeline-old", "2026-11-16T01:00:00+00:00", 0.9, "needs_human", 1),
            ("pipeline-new", "2026-11-16T02:00:00+00:00", 0.7, "pass", 0),
        ):
            insert_eval_bundle(
                {
                    "eval_run_id": run_id,
                    "started_at": time,
                    "layer": "pipeline",
                    "dataset_version": "v0.1",
                    "code_version": "fixture",
                    "prompt_versions": "{}",
                    "model_config": "{}",
                    "repeats": 1,
                    "is_baseline": 0,
                    "summary": json.dumps({"finding_recall": recall}),
                },
                [
                    {
                        "case_id": "case-x",
                        "repeat": 1,
                        "passed": passed,
                        "expected": "{}",
                        "actual": json.dumps({"outcome": outcome}),
                        "metrics": "{}",
                        "run_id": None,
                    }
                ],
                connection=connection,
            )
        insert_eval_bundle(
            {
                "eval_run_id": "consistency-run",
                "started_at": "2026-11-16T03:00:00+00:00",
                "layer": "consistency",
                "dataset_version": "v0.1",
                "code_version": "fixture",
                "prompt_versions": "{}",
                "model_config": "{}",
                "repeats": 5,
                "is_baseline": 0,
                "summary": json.dumps(
                    {
                        "decision_agreement": 0.8,
                        "finding_jaccard": 0.6,
                        "flip_rate": 0.2,
                        "flaky_case_ids": ["flaky-case"],
                        "repeats_per_case": 5,
                    }
                ),
            },
            [
                {
                    "case_id": "flaky-case",
                    "repeat": 1,
                    "passed": 0,
                    "expected": "{}",
                    "actual": "{}",
                    "metrics": json.dumps(
                        {"flaky": True, "decision_agreement": 0.8, "finding_jaccard": 0.6}
                    ),
                    "run_id": None,
                }
            ],
            connection=connection,
        )
    finally:
        connection.close()
    monkeypatch.setenv("DATABASE_PATH", str(sample_path))
    for filename in ("5_Compare_Runs.py", "6_Consistency.py", "10_Judge_Calibration.py"):
        page = REPOSITORY_ROOT / "dashboard" / "pages" / filename
        app = AppTest.from_file(str(page), default_timeout=30).run()
        if filename == "5_Compare_Runs.py" and not app.exception:
            app.selectbox[0].set_value("pipeline-new").run()
        assert not app.exception, f"{page.name}: {app.exception}"
