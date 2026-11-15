# L1 security scanner and secret redactor evaluations.
# Cases combine fixed synthetic snippets and construction-labeled dataset diffs.

from __future__ import annotations

from collections import Counter

from evals.results import SuiteCaseResult
from evals.suites.dataset_cases import load_cases
from mergeguard.checks.redact import redact_diff
from mergeguard.checks.rule_scan import scan_diff

SECRET_SNIPPET_COUNT = 150
REAL_SECRET_COUNT = 100
PLACEHOLDER_COUNT = SECRET_SNIPPET_COUNT - REAL_SECRET_COUNT


def evaluate_secret_scanner() -> tuple[float, float, list[SuiteCaseResult]]:
    """Measure rule-scanner recall on synthetic keys and noise on placeholders."""
    snippets = _secret_snippets()
    results = []
    real_hits = 0
    placeholder_hits = 0
    for index, (snippet, is_secret) in enumerate(snippets):
        findings = scan_diff(_snippet_diff(snippet, index))
        detected = any(item.category == "hardcoded_secret" for item in findings)
        if is_secret:
            real_hits += detected
        else:
            placeholder_hits += detected
        results.append(
            SuiteCaseResult(
                f"l1-secret-{index + 1:03d}",
                1,
                detected == is_secret,
                {"secret": is_secret},
                {"secret": detected},
                {"component": "secret_scanner"},
            )
        )
    return real_hits / REAL_SECRET_COUNT, placeholder_hits / PLACEHOLDER_COUNT, results


def evaluate_pattern_scanner(
    version: str = "v0.1", split: str | None = None, limit: int | None = None
) -> tuple[dict[str, object], list[SuiteCaseResult]]:
    """Report seeded security detection and benign false positives by category."""
    totals: Counter[str] = Counter()
    caught: Counter[str] = Counter()
    false_positives: Counter[str] = Counter()
    results = []
    for record, diff in load_cases(version, split, limit):
        if record["source"] not in {"seeded", "hard_negative", "presumed_clean"}:
            continue
        predicted = sorted({finding.category for finding in scan_diff(diff)})
        expected = [record["category"]] if record["source"] == "seeded" else []
        if expected:
            totals[expected[0]] += 1
            caught[expected[0]] += expected[0] in predicted
        for category in predicted:
            if category not in expected:
                false_positives[category] += 1
        results.append(
            SuiteCaseResult(
                f"l1-pattern-{record['id']}",
                1,
                set(expected) == set(predicted),
                {"categories": expected},
                {"categories": predicted},
                {"component": "pattern_scanner", "source": record["source"]},
            )
        )
    categories = sorted(set(totals) | set(false_positives))
    summary = {
        category: {
            "seeded_total": totals[category],
            "seeded_caught": caught[category],
            "false_positives": false_positives[category],
        }
        for category in categories
    }
    return summary, results


def evaluate_redactor() -> tuple[float, list[SuiteCaseResult]]:
    """Check that 150 synthetic secret values disappear from redacted text."""
    results = []
    removed = 0
    for index in range(SECRET_SNIPPET_COUNT):
        value = f"MGsyntheticSecretValue{index:04d}ABCDE"
        diff = _snippet_diff(f'token = "{value}"', index)
        redacted = redact_diff(diff)
        is_removed = value not in redacted
        removed += is_removed
        results.append(
            SuiteCaseResult(
                f"l1-redactor-{index + 1:03d}",
                1,
                is_removed,
                {"secret_removed": True},
                {"secret_removed": is_removed},
                {"component": "redactor"},
            )
        )
    return removed / SECRET_SNIPPET_COUNT, results


def _secret_snippets() -> list[tuple[str, bool]]:
    """Return 100 synthetic secret formats and 50 safe placeholders."""
    real = [
        (f'api_key = "MG_SYNTHETIC_KEY_{index:06d}_A9z"', True)
        for index in range(REAL_SECRET_COUNT)
    ]
    placeholders = [
        (f'api_key = "example_placeholder_key_{index:04d}"', False)
        for index in range(PLACEHOLDER_COUNT)
    ]
    return real + placeholders


def _snippet_diff(snippet: str, index: int) -> str:
    """Wrap one scanner snippet in an added-line diff."""
    file = f"scanner/snippet_{index:03d}.py"
    return f"diff --git a/{file} b/{file}\n--- a/{file}\n+++ b/{file}\n@@ -0,0 +1 @@\n+{snippet}\n"
