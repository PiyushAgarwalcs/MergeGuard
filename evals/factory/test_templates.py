# Examples of deterministic security-seed generation.
# These tests verify source-derived labels and exact diff evidence.

import ast
from collections import Counter

from evals.factory.templates import (
    DIFFICULTIES,
    SECURITY_CATEGORIES,
    all_templates,
    generate_all_seeds,
)
from mergeguard.checks.diff_parser import parse_diff


def test_template_catalog_has_four_variants_per_security_category() -> None:
    """Every security category has one seed at each planned difficulty."""
    templates = all_templates()
    counts = Counter(template.category for template in templates)

    assert set(counts) == set(SECURITY_CATEGORIES)
    assert all(count == 4 for count in counts.values())
    assert all(
        {item.difficulty for item in templates if item.category == category} == set(DIFFICULTIES)
        for category in SECURITY_CATEGORIES
    )
    assert all(
        len(
            {template.replacements[0][1] for template in templates if template.category == category}
        )
        == 4
        for category in SECURITY_CATEGORIES
    )


def test_generated_seeds_have_parseable_source_and_exact_diff_quotes() -> None:
    """Every case modifies parseable source and quotes an added changed line."""
    seeds = generate_all_seeds()

    assert len(seeds) == 48
    for seed in seeds:
        ast.parse(seed.content)
        hunks = parse_diff(seed.diff)
        assert {hunk.file for hunk in hunks} == {seed.template.file}
        added = [line for hunk in hunks for line in hunk.added if seed.template.quote in line.text]
        assert added
        assert seed.line_start == seed.line_end == added[0].line_no
