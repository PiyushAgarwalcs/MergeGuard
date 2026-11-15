# Wrappers are metamorphic; verifier attacks must fail for their exact reason.
# The fixture generator does not invoke models or alter the checkout.

from collections import Counter

from evals.factory.templates import generate_all_seeds
from evals.factory.wrappers import (
    finding_for_seed,
    generate_injection_wrappers,
    generate_variants,
    generate_verifier_attacks,
)
from mergeguard.checks.diff_parser import parse_diff
from mergeguard.checks.verify_findings import verify_findings


def test_injection_wrappers_cover_all_requested_placements() -> None:
    """Twelve wrappers cover code, README and PR metadata attack surfaces."""
    seeds = generate_all_seeds()
    seed_by_id = {seed.template.case_id: seed for seed in seeds}
    wrappers = generate_injection_wrappers(seeds)

    assert len(wrappers) == 12
    assert {
        "code_comment",
        "docstring",
        "string_literal",
        "filename",
        "commit_message",
        "pr_title",
        "pr_body",
        "readme_change",
    } <= {case.placement for case in wrappers}
    for case in wrappers:
        seed = seed_by_id[case.base_case_id]
        hunks = parse_diff(case.diff)
        assert any(
            hunk.file == seed.template.file
            and any(seed.template.quote in line.text for line in hunk.added)
            for hunk in hunks
        )
        verified, rejected = verify_findings([finding_for_seed(seed)], case.diff)
        assert len(verified) == 1
        assert not rejected
        assert case.marker in (
            case.diff + (case.filename or "") + case.commit_message + case.pr_title + case.pr_body
        )


def test_variants_preserve_all_genuine_seed_findings() -> None:
    """Rename, reformat, reorder and harmless-comment variants remain valid."""
    seeds = generate_all_seeds()
    seed_by_id = {seed.template.case_id: seed for seed in seeds}
    variants = generate_variants(seeds)

    assert {"rename", "reformat", "reordered", "harmless_comment"} <= {
        case.variant for case in variants
    }
    assert len({case.case_id for case in variants}) == len(variants)
    for case in variants:
        findings = [finding_for_seed(seed_by_id[case_id]) for case_id in case.base_case_ids]
        verified, rejected = verify_findings(findings, case.diff)
        assert len(verified) == len(findings), case.case_id
        assert not rejected, case.case_id
        assert Counter(finding.category for finding in verified) == Counter(
            case.expected_categories
        )


def test_verifier_attack_cases_are_rejected_for_expected_reasons() -> None:
    """Fabricated quotes, lines, evidence ids and unchanged context never pass."""
    seeds = generate_all_seeds()
    attacks = generate_verifier_attacks(seeds)

    assert len(attacks) == len(seeds) * 4
    for attack in attacks:
        verified, rejected = verify_findings([attack.finding], attack.diff, attack.context)
        assert not verified, attack.case_id
        assert len(rejected) == 1
        assert rejected[0].reason == attack.expected_rejection
