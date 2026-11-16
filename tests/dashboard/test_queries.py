# Tests dashboard read-only database access and dataset browsing.
# Temporary databases and cases isolate each query behavior.

import sqlite3
from pathlib import Path

import pytest
import yaml

from dashboard.queries import (
    _read_connection,
    dataset_counts,
    latest_eval_run,
    list_eval_results,
    list_eval_runs,
    list_llm_event_summaries,
    load_dataset_cases,
)
from tests.make_sample_db import build_sample_db


def test_dashboard_queries_read_sample_evaluation_database(tmp_path):
    """Read the synthetic run and its linked case result."""
    database = build_sample_db(tmp_path / "sample.db")
    runs = list_eval_runs(path=database)
    results = list_eval_results("sample-eval-run", path=database)
    assert runs[0]["layer"] == "components"
    assert latest_eval_run("components", path=database)["eval_run_id"] == "sample-eval-run"
    assert results[0]["case_id"] == "sec-hardcoded_secret-0001"
    assert list_llm_event_summaries(path=database) == []


def test_dashboard_database_connection_is_read_only(tmp_path):
    """Prevent dashboard SQL from changing the evaluation database."""
    database = build_sample_db(tmp_path / "sample.db")
    connection = _read_connection(database)
    assert connection is not None
    try:
        with pytest.raises(sqlite3.OperationalError):
            connection.execute("DELETE FROM eval_runs")
    finally:
        connection.close()


def test_missing_database_and_dataset_return_empty_data(tmp_path):
    """Show empty states instead of creating missing database or case files."""
    assert list_eval_runs(path=tmp_path / "missing.db") == []
    assert load_dataset_cases("missing", tmp_path) == []


def test_dataset_counts_group_case_metadata(tmp_path):
    """Count loaded cases by source, category, split and tier."""
    _write_case(tmp_path, "case-1", "seeded", "sql_injection", "dev", "canary")
    _write_case(tmp_path, "case-2", "hard_negative", "safe", "test", "standard")
    counts = dataset_counts("v0.1", tmp_path)
    assert counts["total"] == 2
    assert counts["source"] == {"hard_negative": 1, "seeded": 1}
    assert counts["tier"] == {"canary": 1, "standard": 1}


def _write_case(
    root: Path, case_id: str, source: str, category: str, split: str, tier: str
) -> Path:
    """Write the minimal case file needed by dashboard dataset queries."""
    case_dir = root / "v0.1" / "cases" / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    record = {
        "id": case_id,
        "source": source,
        "category": category,
        "split": split,
        "tier": tier,
        "expected_decision": "block",
        "findings": [],
        "provenance": {},
    }
    case_file = case_dir / "case.yml"
    case_file.write_text(yaml.safe_dump(record), encoding="utf-8")
    (case_dir / "change.diff").write_text("+added\n", encoding="utf-8")
    return case_file
