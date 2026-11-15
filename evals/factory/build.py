# Builds and validates the versioned offline evaluation dataset.
# Case labels come from deterministic construction and mechanical evidence.

from __future__ import annotations

import hashlib
import json
import shutil
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path

import yaml
from openai import OpenAIError

from evals.factory.benign import (
    generate_hard_negatives,
    generate_presumed_clean,
)
from evals.factory.benign_gaps import generate_test_gaps
from evals.factory.benign_validation import validate_cases
from evals.factory.build_records import (
    record_from_example,
    record_from_injection,
    record_from_mutation,
    record_from_seed,
    record_from_variant,
    split_for_id,
)
from evals.factory.cross_check import agrees_with_seed, check_seed
from evals.factory.mutations import generate_mutations
from evals.factory.seed_llm import generate_seed
from evals.factory.templates import SAMPLE_ROOT, all_templates, generate_all_seeds
from evals.factory.validate import validate_seed
from evals.factory.wrapper_attacks import generate_verifier_attacks
from evals.factory.wrappers import (
    generate_injection_wrappers,
    generate_variants,
)
from mergeguard.checks.diff_parser import parse_diff
from mergeguard.checks.redact import redact_diff
from mergeguard.checks.rule_scan import scan_diff
from mergeguard.llm_fake import ScriptedLLM
from mergeguard.settings import settings

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


def build_dataset(
    version: str, root: Path = DATASET_ROOT, *, llm: bool = False
) -> dict[str, object]:
    """Generate cases, validate them, and write case files and manifest."""
    if not version.startswith("v") or "/" in version or "\\" in version:
        raise ValueError("Version must be a simple name such as v0.1.")
    if llm and version != "v0.2":
        raise ValueError("LLM-assisted dataset growth is only supported for v0.2.")
    if llm and not (settings.LLM_API_KEY and settings.LLM_BASE_URL):
        return {
            "skipped": True,
            "written": False,
            "message": "LLM credentials are missing; no dataset files were written.",
        }
    if llm:
        _require_independent_models()
    snapshot = _sample_snapshot()
    seeds = generate_all_seeds()
    cases = [record_from_seed(seed, snapshot) for seed in seeds]
    examples = generate_hard_negatives() + generate_presumed_clean() + generate_test_gaps()
    reports = validate_cases(examples)
    invalid = [report.case_id for report in reports if not report.valid]
    if invalid:
        raise ValueError(f"Benign examples failed validation: {', '.join(invalid)}")
    cases.extend(record_from_example(case, snapshot) for case in examples)
    mutations = generate_mutations()
    cases.extend(record_from_mutation(case, snapshot) for case in mutations)
    if len(mutations) != 12:
        raise ValueError(f"Expected 12 test-killed mutations, got {len(mutations)}.")
    injections = generate_injection_wrappers(seeds)
    cases.extend(
        record_from_injection(case, snapshot, seeds[index % len(seeds)].template.difficulty)
        for index, case in enumerate(injections)
    )
    seed_by_id = {seed.template.case_id: seed for seed in seeds}
    variants = generate_variants(seeds)
    cases.extend(
        record_from_variant(
            case,
            {case_id: snapshot for case_id in case.base_case_ids},
            {case_id: seed_by_id[case_id].template.difficulty for case_id in case.base_case_ids},
        )
        for case in variants
    )
    attacks = generate_verifier_attacks(seeds)
    cases.extend(_record_attack(attack, snapshot) for attack in attacks)
    cases = _deduplicate(cases)
    _assign_canaries(cases)
    _refresh_splits(cases)

    review_items: list[dict[str, object]] = []
    if llm:
        generated, review_items = _generate_llm_cases(snapshot)
        cases.extend(generated)

    target = root / version
    if target.exists():
        shutil.rmtree(target)
    case_root = target / "cases"
    review_queue = target / "review_queue"
    case_root.mkdir(parents=True)
    review_queue.mkdir()
    for case in cases:
        case_dir = case_root / str(case["id"])
        case_dir.mkdir()
        diff = str(case.pop("diff"))
        (case_dir / "change.diff").write_text(diff, encoding="utf-8")
        (case_dir / "case.yml").write_text(
            yaml.safe_dump(case, sort_keys=False, allow_unicode=True), encoding="utf-8"
        )
    manifest = _manifest(cases, case_root, version)
    if llm:
        for item in review_items:
            review_path = review_queue / f"{item['id']}.json"
            review_path.write_text(
                json.dumps(item, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
        manifest["notes"] = "Template dataset plus independently checked LLM security seeds."
    (target / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest


def _generate_llm_cases(
    snapshot: str,
    *,
    generator_client: ScriptedLLM | None = None,
    checker_client: ScriptedLLM | None = None,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """Generate, mechanically validate, and independently check one seed per category."""
    previous_mode = settings.LLM_MODE
    settings.LLM_MODE = "record"
    accepted: list[dict[str, object]] = []
    review_items: list[dict[str, object]] = []
    templates_by_category = {}
    for template in all_templates():
        templates_by_category.setdefault(template.category, template)
    try:
        for category, template in templates_by_category.items():
            case_id = f"llm-sec-{category}-v02"
            try:
                generated = generate_seed(template, difficulty="subtle", client=generator_client)
                report = validate_seed(generated)
                if not report.valid or not _synthetic_secret_is_safe(generated.diff, category):
                    review_items.append(
                        _review_item(case_id, category, "validation_failed", generated.diff)
                    )
                    continue
                cross_check = check_seed(generated, checker_client)
                if not agrees_with_seed(generated, cross_check):
                    review_items.append(
                        _review_item(case_id, category, "cross_check_disagreed", generated.diff)
                    )
                    continue
                case = record_from_seed(generated, snapshot)
                case["provenance"]["generated_by"] = settings.GENERATOR_MODEL
                case["provenance"]["cross_check"] = "agreed"
                case["split"] = split_for_id(case_id)
                case["tier"] = "standard"
                accepted.append(case)
            except (OSError, RuntimeError, TypeError, ValueError, OpenAIError) as error:
                review_items.append(
                    {
                        "id": case_id,
                        "category": category,
                        "status": "generation_failed",
                        "error_type": type(error).__name__,
                    }
                )
    finally:
        settings.LLM_MODE = previous_mode
    return accepted, review_items


def _require_independent_models() -> None:
    """Require generator and cross-check model names from different families."""
    checker = settings.CROSS_CHECK_MODEL or settings.SKEPTIC_MODEL
    if _model_family(settings.GENERATOR_MODEL) == _model_family(checker):
        raise ValueError(
            "Configure CROSS_CHECK_MODEL or SKEPTIC_MODEL from a different model family than GENERATOR_MODEL."
        )


def _model_family(model: str) -> str:
    """Map common model name prefixes to provider families for independence checks."""
    name = model.lower().split("/", maxsplit=1)[-1]
    families = {
        "anthropic": ("claude",),
        "google": ("gemini",),
        "meta": ("llama",),
        "mistral": ("mistral", "mixtral"),
        "openai": ("gpt", "o1", "o3", "o4"),
    }
    for family, prefixes in families.items():
        if name.startswith(prefixes):
            return family
    return name.split("-", maxsplit=1)[0]


def _synthetic_secret_is_safe(diff: str, category: str) -> bool:
    """Allow only visibly synthetic key material in generated seed diffs."""
    secrets = [finding for finding in scan_diff(diff) if finding.category == "hardcoded_secret"]
    return not secrets or (
        category == "hardcoded_secret" and all("MG_SYNTHETIC_" in item.quote for item in secrets)
    )


def _review_item(case_id: str, category: str, status: str, diff: str) -> dict[str, object]:
    """Store only redacted patch text and safe status metadata for human review."""
    return {
        "id": case_id,
        "category": category,
        "status": status,
        "diff": redact_diff(diff),
    }


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
            "human_reviewed": False,
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
