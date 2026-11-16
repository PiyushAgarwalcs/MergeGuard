# evals.factory.generation
# Handles optional LLM-generated dataset cases and provider-family checks.

from __future__ import annotations

from typing import Any

from openai import OpenAIError

from evals.factory.build_records import record_from_seed
from evals.factory.cross_check import agrees_with_seed, check_seed
from evals.factory.record_common import split_for_id
from evals.factory.seed_llm import generate_seed
from evals.factory.template_types import SeedTemplate
from evals.factory.templates import all_templates
from evals.factory.validate import validate_seed
from mergeguard.checks.redact import redact_diff
from mergeguard.checks.rule_scan import scan_diff
from mergeguard.llm_fake import ScriptedLLM
from mergeguard.settings import settings


def _generate_llm_cases(
    snapshot: str,
    *,
    generator_client: ScriptedLLM | None = None,
    checker_client: ScriptedLLM | None = None,
    templates: list[SeedTemplate] | None = None,
    seed_validator: Any | None = None,
    secret_is_safe: Any | None = None,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """Generate, mechanically validate, and independently check one seed per category."""
    validate = seed_validator or validate_seed
    check_secret = secret_is_safe or _synthetic_secret_is_safe
    previous_mode = settings.LLM_MODE
    settings.LLM_MODE = "record"
    accepted: list[dict[str, object]] = []
    review_items: list[dict[str, object]] = []
    templates_by_category = {}
    for template in templates or all_templates():
        templates_by_category.setdefault(template.category, template)
    try:
        for category, template in templates_by_category.items():
            case_id = f"llm-sec-{category}-v02"
            try:
                generated = generate_seed(template, difficulty="subtle", client=generator_client)
                report = validate(generated)
                if not report.valid or not check_secret(generated.diff, category):
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
