# Mechanical validation for generated dataset seeds.
# Validation applies diffs as text and runs static analyzers without executing code.

from __future__ import annotations

import ast
import json
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from evals.factory.diff_apply import apply_unified_diff
from evals.factory.template_types import SeededChange
from evals.factory.templates import SAMPLE_ROOT
from mergeguard.checks.diff_parser import parse_diff
from mergeguard.checks.rule_scan import scan_diff

BANDIT_TIMEOUT_SECONDS = 15
BANDIT_RULES = {
    "sql_injection": {"B608"},
    "command_injection": {"B602"},
    "unsafe_deserialization": {"B301"},
    "weak_crypto": {"B324"},
    "tls_verification_disabled": {"B501"},
    "insecure_randomness": {"B311"},
}
RULE_SCAN_CATEGORIES = {"hardcoded_secret", "sensitive_data_in_logs"}


@dataclass(frozen=True)
class ValidationReport:
    """Names of successful, failed, and intentionally skipped checks."""

    passed: tuple[str, ...]
    failures: tuple[str, ...]
    skipped: tuple[str, ...]

    @property
    def valid(self) -> bool:
        """Report whether all applicable validators passed."""
        return not self.failures


def _bandit_ids(content: str) -> set[str]:
    """Run Bandit on a temporary source file and return its rule identifiers."""
    with tempfile.TemporaryDirectory(prefix="mergeguard-seed-") as directory:
        source_path = Path(directory) / "seed.py"
        source_path.write_text(content, encoding="utf-8")
        try:
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "bandit",
                    "--quiet",
                    "--format",
                    "json",
                    str(source_path),
                ],
                capture_output=True,
                check=False,
                text=True,
                timeout=BANDIT_TIMEOUT_SECONDS,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired) as error:
            raise RuntimeError(f"Bandit could not complete: {error}") from error
    try:
        report = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError("Bandit returned invalid JSON output.") from error
    return {finding["test_id"] for finding in report.get("results", [])}


def _static_tool_agrees(seed: SeededChange) -> bool | None:
    """Confirm a known static tool reports the generated category."""
    category = seed.template.category
    if category in BANDIT_RULES:
        return bool(_bandit_ids(seed.content) & BANDIT_RULES[category])
    if category in RULE_SCAN_CATEGORIES:
        return any(finding.category == category for finding in scan_diff(seed.diff))
    return None


def validate_seed(seed: SeededChange, sample_root: Path = SAMPLE_ROOT) -> ValidationReport:
    """Run every applicable mechanical validator for one generated seed."""
    passed: list[str] = []
    failures: list[str] = []
    skipped: list[str] = []
    try:
        ast.parse(seed.content)
        passed.append("parses")
    except SyntaxError:
        failures.append("parses")

    source_path = sample_root / seed.template.sample_repo / seed.template.file
    try:
        original = source_path.read_text(encoding="utf-8")
        applied = apply_unified_diff(original, seed.diff)
        if applied != seed.content:
            raise ValueError("Applied diff differs from generated content.")
        passed.append("applies_cleanly")
    except (OSError, ValueError):
        failures.append("applies_cleanly")

    hunks = parse_diff(seed.diff)
    matching_hunks = [hunk for hunk in hunks if hunk.file == seed.template.file]
    if any(
        hunk.new_start <= seed.line_start <= seed.line_end <= hunk.new_end
        for hunk in matching_hunks
    ):
        passed.append("line_in_diff")
    else:
        failures.append("line_in_diff")

    if any(
        seed.line_start <= line.line_no <= seed.line_end and seed.template.quote in line.text
        for hunk in matching_hunks
        for line in hunk.added
    ):
        passed.append("quote_on_line")
    else:
        failures.append("quote_on_line")

    try:
        static_result = _static_tool_agrees(seed)
    except RuntimeError:
        static_result = False
    if static_result is None:
        skipped.append("static_tool_agrees")
    elif static_result:
        passed.append("static_tool_agrees")
    else:
        failures.append("static_tool_agrees")
    return ValidationReport(tuple(passed), tuple(failures), tuple(skipped))
