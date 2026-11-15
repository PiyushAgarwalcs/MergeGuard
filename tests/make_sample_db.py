# Builds a small SQLite database for dashboard page smoke tests.
# All records are synthetic and contain no secrets or live pull request data.

from __future__ import annotations

import json
import sys
from pathlib import Path

from mergeguard.storage import connect, insert_eval_bundle

DEFAULT_PATH = Path(__file__).resolve().parent / "fixtures" / "sample.db"


def build_sample_db(path: Path = DEFAULT_PATH) -> Path:
    """Create a deterministic database with one evaluation and one case result."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    connection = connect(path)
    try:
        insert_eval_bundle(
            {
                "eval_run_id": "sample-eval-run",
                "started_at": "2026-01-01T00:00:00+00:00",
                "layer": "components",
                "dataset_version": "v0.1",
                "code_version": "sample-commit",
                "prompt_versions": "{}",
                "model_config": json.dumps({"mode": "replay"}),
                "repeats": 1,
                "is_baseline": 0,
                "summary": json.dumps({"judge_truth_table_accuracy": 1.0}),
            },
            [
                {
                    "case_id": "sec-hardcoded_secret-0001",
                    "repeat": 1,
                    "passed": 1,
                    "expected": json.dumps({"outcome": "block"}),
                    "actual": json.dumps({"outcome": "block"}),
                    "metrics": "{}",
                    "run_id": None,
                }
            ],
            connection=connection,
        )
    finally:
        connection.close()
    return path


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PATH
    print(build_sample_db(target))
