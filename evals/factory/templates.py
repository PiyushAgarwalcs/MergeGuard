# Deterministic security-case template rendering.
# Each generated finding is tied to an added line in a minimal unified diff.

from __future__ import annotations

import difflib
from pathlib import Path

from evals.factory.template_patterns_a import patterns as injection_patterns
from evals.factory.template_patterns_b import patterns as data_patterns
from evals.factory.template_patterns_c import patterns as application_patterns
from evals.factory.template_types import CategoryPattern, SeededChange, SeedTemplate
from mergeguard.checks.diff_parser import parse_diff

SAMPLE_ROOT = Path(__file__).resolve().parents[1] / "sample_repos"
DIFFICULTIES = ("obvious", "subtle", "context_dependent", "subtle")
SECURITY_CATEGORIES = (
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
)


def _patterns() -> list[CategoryPattern]:
    """Collect category patterns in stable taxonomy order."""
    groups = injection_patterns() + data_patterns() + application_patterns()
    by_category = {pattern.category: pattern for pattern in groups}
    if set(by_category) != set(SECURITY_CATEGORIES):
        raise ValueError("Template patterns must cover each security category exactly once.")
    return [by_category[category] for category in SECURITY_CATEGORIES]


def all_templates() -> list[SeedTemplate]:
    """Return four deterministic variants for each security category."""
    templates: list[SeedTemplate] = []
    for pattern in _patterns():
        variants = zip(pattern.outputs, pattern.quotes, strict=True)
        for index, (output, quote) in enumerate(variants, start=1):
            templates.append(
                SeedTemplate(
                    case_id=f"sec-{pattern.category}-{index:04d}",
                    category=pattern.category,
                    sample_repo=pattern.sample_repo,
                    file=pattern.file,
                    severity=pattern.severity,
                    difficulty=DIFFICULTIES[index - 1],
                    replacements=((pattern.before, output), *pattern.extra_replacements),
                    quote=quote,
                    explanation=pattern.explanation,
                    suggestion=pattern.suggestion,
                )
            )
    return templates


def generate_seed(template: SeedTemplate, sample_root: Path = SAMPLE_ROOT) -> SeededChange:
    """Apply one template and return its diff and verified added-line range."""
    source_path = sample_root / template.sample_repo / template.file
    original = source_path.read_text(encoding="utf-8")
    updated = original
    for before, after in template.replacements:
        if updated.count(before) != 1:
            raise ValueError(f"{template.case_id}: expected one source match")
        updated = updated.replace(before, after, 1)

    diff_lines = difflib.unified_diff(
        original.splitlines(keepends=True),
        updated.splitlines(keepends=True),
        fromfile=f"a/{template.file}",
        tofile=f"b/{template.file}",
        n=3,
    )
    diff = f"diff --git a/{template.file} b/{template.file}\n" + "".join(diff_lines)
    hunks = parse_diff(diff)
    added_lines = [
        line.line_no for hunk in hunks for line in hunk.added if template.quote in line.text
    ]
    if not added_lines:
        raise ValueError(f"{template.case_id}: quote is not an added diff line")
    line_number = min(added_lines)
    return SeededChange(template, diff, updated, line_number, line_number)


def generate_all_seeds(sample_root: Path = SAMPLE_ROOT) -> list[SeededChange]:
    """Render all security category variants against their sample applications."""
    return [generate_seed(template, sample_root) for template in all_templates()]
