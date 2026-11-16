# evals.factory.stats
# Counts the built dataset by source, category, split, and tier.

from __future__ import annotations

from collections import Counter
from pathlib import Path

import yaml

DATASET_ROOT = Path(__file__).resolve().parents[1] / "datasets"


def dataset_stats(version: str, root: Path = DATASET_ROOT) -> dict[str, object]:
    """Return counts by source, category, split, and tier."""
    records = [
        yaml.safe_load(path.read_text(encoding="utf-8"))
        for path in sorted((root / version / "cases").glob("*/case.yml"))
    ]
    return {
        "total_cases": len(records),
        "by_source": dict(sorted(Counter(item["source"] for item in records).items())),
        "by_category": dict(sorted(Counter(item["category"] for item in records).items())),
        "by_split": dict(sorted(Counter(item["split"] for item in records).items())),
        "by_tier": dict(sorted(Counter(item["tier"] for item in records).items())),
    }
