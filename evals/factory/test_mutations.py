# Examples of mutation generation and regression-test filtering.
# A retained mutation must have an exact changed-line quote and a killed test.

from collections import Counter

from evals.factory.diff_apply import apply_unified_diff
from evals.factory.mutation_specs import all_mutation_specs
from evals.factory.mutations import generate_mutations
from evals.factory.templates import SAMPLE_ROOT
from mergeguard.checks.diff_parser import parse_diff


def test_mutation_plan_covers_six_correctness_categories() -> None:
    """The planned mutation catalog has two cases per correctness category."""
    counts = Counter(spec.category for spec in all_mutation_specs())

    assert len(counts) == 6
    assert set(counts.values()) == {2}


def test_only_test_killed_mutations_are_returned() -> None:
    """Each returned mutation applies cleanly and quotes an added source line."""
    mutations = generate_mutations()

    assert len(mutations) == 12
    for mutation in mutations:
        original_path = SAMPLE_ROOT / mutation.sample_repo / mutation.file
        original = original_path.read_text(encoding="utf-8")
        assert apply_unified_diff(original, mutation.diff) == mutation.content
        added = [
            line
            for hunk in parse_diff(mutation.diff)
            for line in hunk.added
            if mutation.quote in line.text
        ]
        assert added
        assert mutation.line_start == mutation.line_end == added[0].line_no
