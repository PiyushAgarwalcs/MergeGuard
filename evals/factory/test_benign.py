# Generated benign cases preserve labels, quotes and passing sample behavior.
# Each candidate runs against an isolated copy of its sample application.

from collections import Counter
from dataclasses import replace

from evals.factory.benign import (
    generate_hard_negatives,
    generate_presumed_clean,
)
from evals.factory.benign_gaps import generate_test_gaps
from evals.factory.benign_types import ExampleCase
from evals.factory.benign_validation import validate_case, validate_cases
from evals.factory.templates import SAMPLE_ROOT
from mergeguard.checks.diff_parser import parse_diff


def test_benign_catalog_counts_and_test_gap_labels() -> None:
    """The factory matches the planned source counts and all test-gap types."""
    hard_negatives = generate_hard_negatives()
    presumed_clean = generate_presumed_clean()
    test_gaps = generate_test_gaps()

    assert len(hard_negatives) == 20
    assert len(presumed_clean) == 30
    assert len(test_gaps) == 10
    assert Counter(case.kind for case in presumed_clean) == {
        "documentation": 12,
        "refactor": 6,
        "feature": 12,
    }
    assert Counter(case.category for case in test_gaps) == {
        "missing_test": 4,
        "test_coverage": 3,
        "test_weakened": 2,
        "assertion_removed": 1,
    }
    all_cases = hard_negatives + presumed_clean + test_gaps
    assert len({case.case_id for case in all_cases}) == 60
    assert all(case.source == "hard_negative" for case in hard_negatives)
    assert all(case.expected_decision == "allow" for case in presumed_clean)


def test_all_generated_cases_apply_have_evidence_and_pass_sample_tests() -> None:
    """All candidates are exact patches, static-quiet and testable."""
    cases = generate_hard_negatives() + generate_presumed_clean() + generate_test_gaps()

    reports = validate_cases(cases)

    assert len(reports) == 60
    assert all(report.valid for report in reports), [
        (report.case_id, report.failures) for report in reports if not report.valid
    ]
    warning_cases = {
        report.case_id: report.passed
        for report in reports
        if "expected_safe_pattern_warning" in report.passed
    }
    assert "hard-negative-19" in warning_cases


def test_validator_rejects_missing_quote_evidence() -> None:
    """A label cannot survive when its exact quote is absent from the diff."""
    case = generate_presumed_clean()[0]
    invalid_case: ExampleCase = replace(case, quote="not present in this patch")

    report = validate_case(invalid_case, run_tests=False)

    assert "quote_on_line" in report.failures


def test_generated_line_ranges_match_added_quotes() -> None:
    """Every generated case points at a real added line in the declared file."""
    for case in generate_hard_negatives() + generate_presumed_clean() + generate_test_gaps():
        matching = [hunk for hunk in parse_diff(case.diff) if hunk.file == case.file]
        assert any(
            case.line_start <= line.line_no <= case.line_end and case.quote in line.text
            for hunk in matching
            for line in hunk.added
        )
        assert (SAMPLE_ROOT / case.sample_repo / case.file).is_file()
