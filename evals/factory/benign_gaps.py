# Test-gap examples distinguish missing coverage from weakened assertions.
# Test changes remain parseable and leave the sample test suite runnable.

from pathlib import Path

from evals.factory.benign_build import append_content, build_case, replace_once
from evals.factory.benign_gap_patterns import (
    ASSERTION_REMOVAL_FEATURES,
    MISSING_TEST_FEATURES,
    REMOVED_ASSERTIONS,
    TESTED_FEATURES,
    WEAKENED_ASSERTIONS,
)
from evals.factory.benign_types import ExampleCase
from evals.factory.templates import SAMPLE_ROOT


def generate_test_gaps(sample_root: Path = SAMPLE_ROOT) -> list[ExampleCase]:
    """Return four missing, three tested, two weakened and one removed case."""
    cases = _generate_missing_tests(sample_root)
    cases.extend(_generate_tested_features(sample_root))
    cases.extend(
        _generate_test_edits(
            WEAKENED_ASSERTIONS[:2],
            (MISSING_TEST_FEATURES[0], MISSING_TEST_FEATURES[2]),
            "test_weakened",
            "weakened",
            sample_root,
        )
    )
    cases.extend(
        _generate_test_edits(
            REMOVED_ASSERTIONS[:1],
            ASSERTION_REMOVAL_FEATURES[:1],
            "assertion_removed",
            "assertion-removed",
            sample_root,
        )
    )
    if len(cases) != 10:
        raise ValueError("The test-gap catalog must contain exactly 10 cases.")
    return cases


def _generate_missing_tests(sample_root: Path) -> list[ExampleCase]:
    """Add logic without changing any test file."""
    cases = []
    for index, (repo, file, snippet, quote) in enumerate(MISSING_TEST_FEATURES, start=1):
        original = (sample_root / repo / file).read_text(encoding="utf-8")
        cases.append(
            build_case(
                f"test-gap-missing-{index:02d}",
                "test_gap",
                "missing_test",
                "missing_test",
                repo,
                ((file, append_content(original, snippet)),),
                file,
                quote,
                "review",
                sample_root,
            )
        )
    return cases


def _generate_tested_features(sample_root: Path) -> list[ExampleCase]:
    """Add small features and the tests that cover them."""
    cases = []
    for index, (repo, source_file, feature, quote, test_file, test) in enumerate(
        TESTED_FEATURES, start=1
    ):
        source = (sample_root / repo / source_file).read_text(encoding="utf-8")
        tests = (sample_root / repo / test_file).read_text(encoding="utf-8")
        cases.append(
            build_case(
                f"test-gap-covered-{index:02d}",
                "test_gap",
                "test_coverage",
                "tested_feature",
                repo,
                (
                    (source_file, append_content(source, feature)),
                    (test_file, append_content(tests, test)),
                ),
                source_file,
                quote,
                "allow",
                sample_root,
            )
        )
    return cases


def _generate_test_edits(
    assertions: tuple[tuple[str, str, str, str], ...],
    features: tuple[tuple[str, str, str, str], ...],
    category: str,
    case_prefix: str,
    sample_root: Path,
) -> list[ExampleCase]:
    """Pair a logic change with one weakened or removed test assertion."""
    cases = []
    for index, ((repo, test_file, before, after), feature) in enumerate(
        zip(assertions, features, strict=True), start=1
    ):
        feature_repo, source_file, snippet, quote = feature
        if repo != feature_repo:
            raise ValueError("Test-gap feature and test repository do not match.")
        source = (sample_root / repo / source_file).read_text(encoding="utf-8")
        tests = (sample_root / repo / test_file).read_text(encoding="utf-8")
        updated_tests = replace_once(tests, before, after)
        cases.append(
            build_case(
                f"test-gap-{case_prefix}-{index:02d}",
                "test_gap",
                category,
                case_prefix,
                repo,
                (
                    (source_file, append_content(source, snippet)),
                    (test_file, updated_tests),
                ),
                source_file,
                quote,
                "review",
                sample_root,
            )
        )
    return cases
