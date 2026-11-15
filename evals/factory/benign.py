# Hard-negative, presumed-clean and test-gap dataset case generation.
# Labels and quote locations are deterministic consequences of each template.

from __future__ import annotations

from pathlib import Path

from evals.factory.benign_build import append_content, build_case, replace_once
from evals.factory.benign_clean_patterns import FEATURES, REFACTORS
from evals.factory.benign_hard_negative_patterns import HARD_NEGATIVE_PATTERNS
from evals.factory.benign_test_patterns import PRESUMED_CLEAN_TESTS
from evals.factory.benign_types import ExampleCase
from evals.factory.templates import SAMPLE_ROOT

README_VARIANTS = (
    ("notes_api", "A compact notes service demonstrates user-scoped records and validation."),
    ("notes_api", "The fixture uses isolated SQLite state for repeatable API examples."),
    ("notes_api", "Examples focus on private notes and predictable service behavior."),
    ("notes_api", "This sample keeps transport concerns outside its core service."),
    ("url_shortener", "A compact link service demonstrates owner-scoped mappings."),
    ("url_shortener", "The fixture uses isolated storage and deterministic test destinations."),
    ("url_shortener", "Examples focus on URL validation and bounded preview behavior."),
    ("url_shortener", "This sample separates link policy from persistence."),
    ("csv_report", "A compact report tool demonstrates safe local file handling."),
    ("csv_report", "The fixture uses temporary files and deterministic CSV formatting."),
    ("csv_report", "Examples focus on validated input and escaped report output."),
    ("csv_report", "This sample separates aggregation from report orchestration."),
)
BASE_DESCRIPTIONS = {
    "notes_api": "Small user-scoped notes service used for offline review evaluation.",
    "url_shortener": "Small owner-scoped link service used for offline review evaluation.",
    "csv_report": "Small local reporting utility used for offline review evaluation.",
}
REFACTOR_TEST_INDICES = (0, 1, 6, 7, 12, 13)
FEATURE_TEST_INDICES = (2, 3, 4, 5, 8, 9, 10, 11, 14, 15, 16, 17)


def generate_hard_negatives(sample_root: Path = SAMPLE_ROOT) -> list[ExampleCase]:
    """Return twenty risky-looking but safe-by-construction examples."""
    cases = []
    for index, (category, repo, file, snippet) in enumerate(HARD_NEGATIVE_PATTERNS, start=1):
        helper = snippet.replace("safe_", f"safe_negative_{index:02d}_", 1)
        quote = helper.splitlines()[0]
        original = (sample_root / repo / file).read_text(encoding="utf-8")
        cases.append(
            build_case(
                f"hard-negative-{index:02d}",
                "hard_negative",
                category,
                "safe_pattern",
                repo,
                ((file, append_content(original, helper)),),
                file,
                quote,
                "allow",
                sample_root,
            )
        )
    if len(cases) != 20:
        raise ValueError("The hard-negative catalog must contain exactly 20 cases.")
    return cases


def generate_presumed_clean(sample_root: Path = SAMPLE_ROOT) -> list[ExampleCase]:
    """Return twelve documentation and eighteen tested-code examples."""
    cases: list[ExampleCase] = []
    for index, (repo, description) in enumerate(README_VARIANTS, start=1):
        file = "README.md"
        original = (sample_root / repo / file).read_text(encoding="utf-8")
        updated = replace_once(original, BASE_DESCRIPTIONS[repo], description)
        cases.append(
            build_case(
                f"presumed-clean-docs-{index:02d}",
                "presumed_clean",
                "clean",
                "documentation",
                repo,
                ((file, updated),),
                file,
                description,
                "allow",
                sample_root,
            )
        )

    for index, (refactor, test_index) in enumerate(
        zip(REFACTORS, REFACTOR_TEST_INDICES, strict=True), start=1
    ):
        repo, source_file, before, after = refactor
        test_repo, test_file, test = PRESUMED_CLEAN_TESTS[test_index]
        if repo != test_repo:
            raise ValueError("Clean refactor and test repositories do not match.")
        source = (sample_root / repo / source_file).read_text(encoding="utf-8")
        tests = (sample_root / repo / test_file).read_text(encoding="utf-8")
        updated_source = replace_once(source, before, after)
        helper = test.replace("test_clean_", f"test_presumed_clean_{index:02d}_", 1)
        cases.append(
            build_case(
                f"presumed-clean-code-{index:02d}",
                "presumed_clean",
                "clean",
                "refactor",
                repo,
                (
                    (source_file, updated_source),
                    (test_file, append_content(tests, helper)),
                ),
                source_file,
                after.splitlines()[-1].strip(),
                "allow",
                sample_root,
            )
        )

    for index, (feature, test_index) in enumerate(
        zip(FEATURES, FEATURE_TEST_INDICES, strict=True), start=7
    ):
        repo, source_file, feature_code, feature_name, module, assertion = feature
        test_repo, test_file, test = PRESUMED_CLEAN_TESTS[test_index]
        if repo != test_repo:
            raise ValueError("Clean feature and test repositories do not match.")
        source = (sample_root / repo / source_file).read_text(encoding="utf-8")
        tests = (sample_root / repo / test_file).read_text(encoding="utf-8")
        helper = _add_feature_assertion(test, module, feature_name, assertion, index)
        cases.append(
            build_case(
                f"presumed-clean-code-{index:02d}",
                "presumed_clean",
                "clean",
                "feature",
                repo,
                (
                    (source_file, append_content(source, feature_code)),
                    (test_file, append_content(tests, helper)),
                ),
                source_file,
                feature_code.splitlines()[0],
                "allow",
                sample_root,
            )
        )
    if len(cases) != 30:
        raise ValueError("The presumed-clean catalog must contain exactly 30 cases.")
    return cases


def _add_feature_assertion(
    test: str, module: str, feature_name: str, assertion: str, index: int
) -> str:
    """Make one existing clean test also exercise its added helper."""
    header, body = test.split("\n", 1)
    test_name = header.replace("test_clean_", f"test_presumed_clean_{index:02d}_", 1)
    addition = f"    from {module} import {feature_name}\n    assert {assertion}\n"
    return f"{test_name}\n{addition}{body}"
