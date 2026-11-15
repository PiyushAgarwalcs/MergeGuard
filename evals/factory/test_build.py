# Tests for dataset construction rules and the on-disk validation contract.
# Small records keep these checks independent of the slower full dataset build.

import hashlib
import json

import yaml

from evals.factory.build import (
    CANARY_CATEGORIES,
    _assign_canaries,
    _deduplicate,
    validate_dataset,
)
from evals.factory.build_records import split_for_id


def test_dataset_split_is_stable_for_case_id():
    """Assign a case to the fixed hash-derived split."""
    assert split_for_id("sec-sql_injection-0001") == "test"


def test_deduplication_preserves_constructed_labels():
    """Deduplicate representation variants without deleting labeled examples."""
    identical = "diff --git a/a.py b/a.py\n+value = 1\n-value = 2\n"
    cases = [
        {"id": "safe-a", "source": "hard_negative", "category": "sql_injection", "diff": identical},
        {"id": "safe-b", "source": "hard_negative", "category": "sql_injection", "diff": identical},
        {"id": "variant-a", "source": "variant", "category": "sql_injection", "diff": identical},
        {"id": "variant-b", "source": "variant", "category": "sql_injection", "diff": identical},
    ]

    retained = _deduplicate(cases)

    assert [case["id"] for case in retained] == ["safe-a", "safe-b", "variant-a"]


def test_canary_selection_covers_fixed_categories():
    """Mark one must-catch record for each required canary category."""
    cases = [
        {"category": category, "must_catch": True, "tier": "standard"}
        for category in CANARY_CATEGORIES
    ]

    _assign_canaries(cases)

    assert sum(case["tier"] == "canary" for case in cases) == 15


def test_dataset_validator_checks_evidence_and_split(tmp_path):
    """Accept cases when evidence, hash split, manifest, and canaries agree."""
    dataset = tmp_path / "v0.1"
    diff = (
        "diff --git a/app.py b/app.py\n--- a/app.py\n+++ b/app.py\n"
        "@@ -1 +1 @@\n-old = 1\n+value = 2\n"
    )
    hashes = {}
    for index in range(15):
        case_id = f"example-case-{index:02d}"
        case_dir = dataset / "cases" / case_id
        case_dir.mkdir(parents=True)
        (case_dir / "change.diff").write_text(diff, encoding="utf-8")
        record = {
            "id": case_id,
            "split": split_for_id(case_id),
            "must_catch": index == 0,
            "tier": "canary",
            "source": "seeded",
            "findings": (
                [{"file": "app.py", "line_start": 1, "line_end": 1, "quote": "value = 2"}]
                if index == 0
                else []
            ),
        }
        case_bytes = yaml.safe_dump(record).encode("utf-8")
        diff_bytes = (case_dir / "change.diff").read_bytes()
        (case_dir / "case.yml").write_bytes(case_bytes)
        hashes[case_id] = hashlib.sha256(case_bytes + b"\0" + diff_bytes).hexdigest()
    (dataset / "review_queue").mkdir()
    (dataset / "manifest.json").write_text(
        json.dumps({"total_cases": 15, "canary_count": 15, "cases": hashes}),
        encoding="utf-8",
    )

    assert validate_dataset("v0.1", tmp_path) == []
