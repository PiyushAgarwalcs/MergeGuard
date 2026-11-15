# Mechanical validation for safe, presumed-clean and test-gap examples.
# Sample tests run only in temporary copies of their application.

from __future__ import annotations

import ast
from pathlib import Path

from evals.factory.benign_test_runner import run_case_tests, run_grouped_tests
from evals.factory.benign_types import CaseValidation, ExampleCase
from evals.factory.diff_apply import apply_unified_diff
from evals.factory.mutations import TEST_DIRECTORIES
from evals.factory.templates import SAMPLE_ROOT
from evals.factory.validate import _bandit_ids
from mergeguard.checks.diff_parser import parse_diff
from mergeguard.checks.rule_scan import scan_diff


def validate_case(
    case: ExampleCase,
    sample_root: Path = SAMPLE_ROOT,
    run_tests: bool = True,
) -> CaseValidation:
    """Check patch fidelity, exact evidence, static quietness and app tests."""
    passed: list[str] = []
    failures: list[str] = []
    source_files = dict(case.changes)

    try:
        for file, patch in case.patches:
            original = (sample_root / case.sample_repo / file).read_text(encoding="utf-8")
            if apply_unified_diff(original, patch) != source_files[file]:
                raise ValueError("applied content differs")
        passed.append("applies_cleanly")
    except (OSError, ValueError, KeyError):
        failures.append("applies_cleanly")

    matching = [hunk for hunk in parse_diff(case.diff) if hunk.file == case.file]
    evidence = [
        line
        for hunk in matching
        for line in hunk.added
        if case.line_start <= line.line_no <= case.line_end and case.quote in line.text
    ]
    if evidence:
        passed.append("quote_on_line")
    else:
        failures.append("quote_on_line")

    syntax_ok = True
    for file, content in case.changes:
        if file.endswith(".py"):
            try:
                ast.parse(content)
            except SyntaxError:
                syntax_ok = False
                break
    if syntax_ok:
        passed.append("parses")
    else:
        failures.append("parses")

    rule_categories = {finding.category for finding in scan_diff(case.diff)}
    expected_rule_categories = (
        {case.category}
        if case.source == "hard_negative" and case.category == "sensitive_data_in_logs"
        else set()
    )
    if rule_categories != expected_rule_categories:
        failures.append("rule_scan_quiet")
    elif rule_categories:
        passed.append("expected_safe_pattern_warning")
    else:
        passed.append("rule_scan_quiet")

    if case.source == "presumed_clean" and _bandit_adds_findings(case, sample_root):
        failures.append("bandit_quiet")
    elif case.source == "presumed_clean":
        passed.append("bandit_quiet")

    if run_tests:
        result = run_case_tests(case, sample_root)
        if result.returncode == 0:
            passed.append("sample_tests")
        else:
            failures.append("sample_tests")
    return CaseValidation(case.case_id, tuple(passed), tuple(failures))


def _bandit_adds_findings(case: ExampleCase, sample_root: Path) -> bool:
    """Reject new Bandit rule types while ignoring expected test assertions."""
    for file, updated in case.changes:
        if not file.endswith(".py"):
            continue
        original = (sample_root / case.sample_repo / file).read_text(encoding="utf-8")
        introduced = _bandit_ids(updated) - _bandit_ids(original) - {"B101"}
        if introduced:
            return True
    return False


def validate_cases(
    cases: list[ExampleCase],
    sample_root: Path = SAMPLE_ROOT,
    run_tests: bool = True,
) -> list[CaseValidation]:
    """Validate a generated collection without modifying the checkout."""
    if any(case.sample_repo not in TEST_DIRECTORIES for case in cases):
        raise ValueError("Every example must target a registered sample application.")
    reports = [validate_case(case, sample_root, False) for case in cases]
    if not run_tests:
        return reports
    test_status = run_grouped_tests(cases, sample_root)
    return [
        CaseValidation(
            report.case_id,
            report.passed + (("sample_tests",) if test_status[case.sample_repo] else ()),
            report.failures + (() if test_status[case.sample_repo] else ("sample_tests",)),
        )
        for case, report in zip(cases, reports, strict=True)
    ]
