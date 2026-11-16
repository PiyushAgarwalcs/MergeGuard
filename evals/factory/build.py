# Builds and validates the versioned offline evaluation dataset.
# Case labels come from deterministic construction and mechanical evidence.

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import yaml

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
)
from evals.factory.generation import (
    _generate_llm_cases as _generate_llm_cases_impl,
)
from evals.factory.generation import (
    _require_independent_models,
    _synthetic_secret_is_safe,
    validate_seed,
)
from evals.factory.mutations import generate_mutations
from evals.factory.stats import dataset_stats  # noqa: F401 - retained public factory export
from evals.factory.templates import all_templates, generate_all_seeds
from evals.factory.validation import (
    CANARY_CATEGORIES,  # noqa: F401 - retained public factory export
    _assign_canaries,
    _deduplicate,
    _manifest,
    _record_attack,
    _refresh_splits,
    _sample_snapshot,
    validate_dataset,  # noqa: F401 - retained public factory export
)
from evals.factory.wrapper_attacks import generate_verifier_attacks
from evals.factory.wrappers import (
    generate_injection_wrappers,
    generate_variants,
)
from mergeguard.settings import settings

DATASET_ROOT = Path(__file__).resolve().parents[1] / "datasets"


def _generate_llm_cases(
    snapshot: str, **kwargs: Any
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """Expose generation through the factory module's stable patch points."""
    kwargs.setdefault("templates", all_templates())
    return _generate_llm_cases_impl(
        snapshot,
        seed_validator=validate_seed,
        secret_is_safe=_synthetic_secret_is_safe,
        **kwargs,
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
