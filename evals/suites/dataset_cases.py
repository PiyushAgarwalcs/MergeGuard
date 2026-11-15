# Reads versioned dataset files for deterministic component evaluation.
# The case YAML is trusted test data; changed code is never executed.

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

DATASET_ROOT = Path(__file__).resolve().parents[1] / "datasets"


def load_cases(
    version: str = "v0.1", split: str | None = None, limit: int | None = None
) -> list[tuple[dict[str, Any], str]]:
    """Load case metadata and text diffs in stable case-id order."""
    case_files = sorted((DATASET_ROOT / version / "cases").glob("*/case.yml"))
    loaded = []
    for path in case_files:
        record = yaml.safe_load(path.read_text(encoding="utf-8"))
        if split is not None and record.get("split") != split:
            continue
        diff = (path.parent / "change.diff").read_text(encoding="utf-8")
        loaded.append((record, diff))
    return loaded[:limit] if limit is not None else loaded
