# evals.factory.validation
# Validates generated dataset records, splits, canaries, and manifest hashes.

from __future__ import annotations

import hashlib
import json
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path

import yaml

from evals.factory.build_records import split_for_id
from evals.factory.templates import SAMPLE_ROOT
from mergeguard.checks.diff_parser import parse_diff

DATASET_ROOT = Path(__file__).resolve().parents[1] / "datasets"
CANARY_CATEGORIES = (
    "hardcoded_secret",
    "sql_injection",
    "command_injection",
    "path_traversal",
    "unsafe_deserialization",
    "ssrf",
    "weak_crypto",
    "tls_verification_disabled",
    "xss",
    "missing_authorization",
    "insecure_randomness",
    "sensitive_data_in_logs",
    "off_by_one",
    "wrong_condition",
    "missing_null_check",
)


def validate_dataset(version: str, root: Path = DATASET_ROOT) -> list[str]:
    """Validate every stored case's contract, split, diff, and evidence."""
    target = root / version
    errors: list[str] = []
    content_hashes: dict[str, str] = {}
    canary_count = 0
    for case_file in sorted((target / "cases").glob("*/case.yml")):
        case_id = case_file.parent.name
        try:
            record = yaml.safe_load(case_file.read_text(encoding="utf-8"))
            diff_path = case_file.parent / "change.diff"
            diff_bytes = diff_path.read_bytes()
            diff = diff_bytes.decode("utf-8")
            content_hashes[case_id] = hashlib.sha256(
                case_file.read_bytes() + b"\0" + diff_bytes
            ).hexdigest()
            canary_count += record.get("tier") == "canary"
            if record["id"] != case_id or record["split"] != split_for_id(case_id):
                raise ValueError("id or hash split mismatch")
            hunks = parse_diff(diff)
            if record["must_catch"] and not record["findings"]:
                raise ValueError("must_catch case has no finding")
            findings = [] if record["source"] == "verifier_attack" else record["findings"]
            for finding in findings:
                if not any(
                    hunk.file == finding["file"]
                    and hunk.new_start
                    <= finding["line_start"]
                    <= finding["line_end"]
                    <= hunk.new_end
                    and any(
                        finding["line_start"] <= line.line_no <= finding["line_end"]
                        and finding["quote"] in line.text
                        for line in hunk.added
                    )
                    for hunk in hunks
                ):
                    raise ValueError("finding quote or line is absent from diff")
        except (OSError, KeyError, TypeError, ValueError, yaml.YAMLError) as error:
            errors.append(f"{case_id}: {error}")
    manifest_path = target / "manifest.json"
    if not manifest_path.exists():
        errors.append("manifest.json is missing")
    else:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        count = len(list((target / "cases").glob("*/case.yml")))
        if manifest.get("total_cases") != count:
            errors.append("manifest total_cases does not match case files")
        if manifest.get("cases") != content_hashes:
            errors.append("manifest case hashes do not match case files")
        if manifest.get("canary_count") != canary_count or canary_count != 15:
            errors.append("manifest must describe exactly 15 canary cases")
    if not (target / "review_queue").is_dir():
        errors.append("review_queue directory is missing")
    return errors


def _sample_snapshot() -> str:
    """Hash all sample app files to identify the exact dataset base."""
    digest = hashlib.sha256()
    for path in sorted(SAMPLE_ROOT.rglob("*")):
        if path.is_file() and ".pytest_cache" not in path.parts and "__pycache__" not in path.parts:
            digest.update(path.relative_to(SAMPLE_ROOT).as_posix().encode())
            digest.update(path.read_bytes())
    return f"sample_repos@{digest.hexdigest()}"


def _deduplicate(cases: list[dict[str, object]]) -> list[dict[str, object]]:
    """Drop same-source cases with over 90 percent normalized diff similarity."""
    retained: list[dict[str, object]] = []
    for case in cases:
        if case["source"] != "variant":
            retained.append(case)
            continue
        normalized = _normalize_diff(str(case["diff"]))
        duplicate = any(
            prior["source"] == "variant"
            and case["category"] == prior["category"]
            and SequenceMatcher(None, normalized, _normalize_diff(str(prior["diff"]))).ratio() > 0.9
            for prior in retained
        )
        if not duplicate:
            retained.append(case)
    return retained


def _normalize_diff(diff: str) -> str:
    """Remove patch headers, whitespace, and identifiers for similarity checks."""
    return "".join(line[1:].strip() for line in diff.splitlines() if line.startswith(("+", "-")))


def _assign_canaries(cases: list[dict[str, object]]) -> None:
    """Mark one must-catch case from each of fifteen fixed categories."""
    for category in CANARY_CATEGORIES:
        match = next(
            (case for case in cases if case["category"] == category and case["must_catch"]),
            None,
        )
        if match is None:
            raise ValueError(f"No must-catch case available for canary category {category}.")
        match["tier"] = "canary"


def _refresh_splits(cases: list[dict[str, object]]) -> None:
    """Recompute split after all generated case ids are finalized."""
    for case in cases:
        case["split"] = split_for_id(str(case["id"]))


def _record_attack(attack: object, snapshot: str) -> dict[str, object]:
    """Represent a verifier attack as an expected rejection case."""
    finding = attack.finding
    return {
        "id": attack.case_id,
        "source": "verifier_attack",
        "split": split_for_id(attack.case_id),
        "tier": "standard",
        "difficulty": "obvious",
        "repo_snapshot": snapshot,
        "category": finding.category,
        "expected_decision": "reject_finding",
        "must_catch": False,
        "findings": [
            {
                "category": finding.category,
                "severity": finding.severity.value,
                "file": finding.file,
                "line_start": finding.line_start,
                "line_end": finding.line_end,
                "quote": finding.quote,
            }
        ],
        "expected_rejection": attack.expected_rejection,
        "attack": attack.attack,
        "provenance": {
            "generated_by": "verifier_attack",
            "validators_passed": ["known_rejection"],
            "cross_check": "skipped_no_model",
        },
        "diff": attack.diff,
    }


def _manifest(cases: list[dict[str, object]], case_root: Path, version: str) -> dict[str, object]:
    """Create source/category counts and per-case content hashes."""
    hashes = {}
    for case in cases:
        case_id = str(case["id"])
        yaml_bytes = (case_root / case_id / "case.yml").read_bytes()
        diff_bytes = (case_root / case_id / "change.diff").read_bytes()
        hashes[case_id] = hashlib.sha256(yaml_bytes + b"\0" + diff_bytes).hexdigest()
    return {
        "version": version,
        "total_cases": len(cases),
        "counts_by_source": dict(sorted(Counter(str(c["source"]) for c in cases).items())),
        "counts_by_category": dict(sorted(Counter(str(c["category"]) for c in cases).items())),
        "counts_by_split": dict(sorted(Counter(str(c["split"]) for c in cases).items())),
        "canary_count": sum(c["tier"] == "canary" for c in cases),
        "cases": hashes,
        "notes": "Template-built v0.1; model cross-check skipped because no credential is configured.",
    }
