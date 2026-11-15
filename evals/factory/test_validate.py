# Examples of mechanical dataset validation and rejection behavior.
# Static analysis scans generated source without importing or executing it.

from dataclasses import replace

import pytest

from evals.factory.diff_apply import apply_unified_diff
from evals.factory.templates import generate_all_seeds
from evals.factory.validate import (
    _static_tool_agrees,
    validate_seed,
)


def test_generated_seeds_pass_applicable_validators() -> None:
    """All template cases parse, apply, and match their exact evidence."""
    for seed in generate_all_seeds():
        report = validate_seed(seed)

        assert report.valid, (seed.template.case_id, report.failures)
        assert {"parses", "applies_cleanly", "line_in_diff", "quote_on_line"} <= set(report.passed)


def test_validator_rejects_source_that_does_not_parse() -> None:
    """Syntax errors fail the parse validator."""
    seed = generate_all_seeds()[0]

    report = validate_seed(replace(seed, content="def broken(:\n"))

    assert "parses" in report.failures


def test_validator_rejects_diff_that_does_not_apply() -> None:
    """A diff whose result disagrees with generated content is rejected."""
    seed = generate_all_seeds()[0]

    report = validate_seed(replace(seed, content="different but parseable = True\n"))

    assert "applies_cleanly" in report.failures


def test_validator_rejects_claimed_lines_outside_the_hunk() -> None:
    """Finding line metadata must be inside the changed hunk."""
    seed = generate_all_seeds()[0]

    report = validate_seed(replace(seed, line_start=999, line_end=999))

    assert "line_in_diff" in report.failures


def test_validator_rejects_quote_not_on_claimed_added_line() -> None:
    """The evidence quote must match an added line at its claimed location."""
    seed = generate_all_seeds()[0]
    template = replace(seed.template, quote="not present in this diff")

    report = validate_seed(replace(seed, template=template))

    assert "quote_on_line" in report.failures


def test_static_validator_rejects_case_without_rule_evidence() -> None:
    """A secret case without a scanner finding fails static agreement."""
    seed = generate_all_seeds()[0]

    assert _static_tool_agrees(replace(seed, diff="")) is False


def test_diff_application_rejects_mismatched_context() -> None:
    """A hunk cannot be applied to unrelated source content."""
    diff = "--- a/sample.py\n+++ b/sample.py\n@@ -1 +1 @@\n-old\n+new\n"

    with pytest.raises(ValueError, match="context"):
        apply_unified_diff("different\n", diff)
