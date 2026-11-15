# Convert generated examples into the versioned YAML case contract.
# Evidence is located in each final diff, not copied from model output.

from __future__ import annotations

from evals.factory.benign_types import ExampleCase
from evals.factory.mutation_types import MutationCase
from evals.factory.template_types import SeededChange
from evals.factory.wrapper_types import InjectionCase, VariantCase
from mergeguard.checks.diff_parser import parse_diff


def record_from_seed(seed: SeededChange, snapshot: str) -> dict[str, object]:
    """Create one must-catch security seed record."""
    finding = _finding(
        seed.template.category,
        seed.template.severity,
        seed.template.file,
        seed.template.quote,
        seed.line_start,
        seed.diff,
    )
    return _record(
        seed.template.case_id,
        "seeded",
        seed.template.category,
        seed.template.difficulty,
        snapshot,
        seed.diff,
        "block" if seed.template.severity == "critical" else "needs_human",
        True,
        "template",
        ["parses", "applies_cleanly", "line_in_diff", "quote_on_line", "static_tool_agrees"],
        [finding],
    )


def record_from_example(case: ExampleCase, snapshot: str) -> dict[str, object]:
    """Create a benign or test-gap case with its construction label."""
    findings = []
    if case.expected_decision == "review":
        severity = "medium" if case.category != "missing_test" else "high"
        findings.append(
            _finding(
                case.category,
                severity,
                case.file,
                case.quote,
                case.line_start,
                case.diff,
            )
        )
    decision = "pass" if case.expected_decision == "allow" else "needs_human"
    passed = ["applies_cleanly", "quote_on_line", "rule_scan_quiet", "sample_tests"]
    return _record(
        case.case_id,
        case.source,
        case.category,
        "context_dependent" if case.source == "presumed_clean" else "subtle",
        snapshot,
        case.diff,
        decision,
        bool(findings),
        "template",
        passed,
        findings,
    )


def record_from_mutation(case: MutationCase, snapshot: str) -> dict[str, object]:
    """Create a correctness case whose label is a failing existing test."""
    finding = _finding(case.category, "medium", case.file, case.quote, case.line_start, case.diff)
    return _record(
        case.case_id,
        "mutation",
        case.category,
        "subtle",
        snapshot,
        case.diff,
        "needs_human",
        True,
        "ast_mutation",
        ["parses", "applies_cleanly", "quote_on_line", "sample_tests_fail"],
        [finding],
    )


def record_from_injection(case: InjectionCase, snapshot: str, difficulty: str):
    """Create a metamorphic PR case using its wrapped seed labels."""
    line = _added_line(case.diff, case.expected_file, case.expected_quote)
    finding = _finding(
        case.expected_category,
        "high",
        case.expected_file,
        case.expected_quote,
        line,
        case.diff,
    )
    record = _record(
        case.case_id,
        "injection",
        case.expected_category,
        difficulty,
        snapshot,
        case.diff,
        "needs_human",
        True,
        "template_wrapper",
        ["quote_on_line", "metamorphic_label_preserved"],
        [finding],
    )
    record["injection"] = {
        "placement": case.placement,
        "goal": case.goal,
        "marker": case.marker,
        "filename": case.filename,
        "commit_message": case.commit_message,
        "pr_title": case.pr_title,
        "pr_body": case.pr_body,
    }
    return record


def record_from_variant(
    case: VariantCase, snapshots: dict[str, str], difficulties: dict[str, str]
) -> dict[str, object]:
    """Create a separately reported label-preserving variant record."""
    findings = []
    for category, file, quote, base_id in zip(
        case.expected_categories,
        case.expected_files,
        case.expected_quotes,
        case.base_case_ids,
        strict=True,
    ):
        line = _added_line(case.diff, file, quote)
        severity = "high"
        findings.append(_finding(category, severity, file, quote, line, case.diff))
    snapshot = snapshots[case.base_case_ids[0]]
    decision = (
        "block" if any(item["severity"] == "critical" for item in findings) else "needs_human"
    )
    record = _record(
        case.case_id,
        "variant",
        "multiple" if len(findings) > 1 else findings[0]["category"],
        difficulties[case.base_case_ids[0]],
        snapshot,
        case.diff,
        decision,
        True,
        "metamorphic_variant",
        ["quote_on_line", "metamorphic_label_preserved"],
        findings,
    )
    record["variant"] = case.variant
    return record


def _record(
    case_id: str,
    source: str,
    category: str,
    difficulty: str,
    snapshot: str,
    diff: str,
    decision: str,
    must_catch: bool,
    generated_by: str,
    validators: list[str],
    findings: list[dict[str, object]],
) -> dict[str, object]:
    """Create common case metadata and deterministic split assignment."""
    return {
        "id": case_id,
        "source": source,
        "split": split_for_id(case_id),
        "tier": "standard",
        "difficulty": difficulty,
        "repo_snapshot": snapshot,
        "category": category,
        "expected_decision": decision,
        "must_catch": must_catch,
        "findings": findings,
        "provenance": {
            "generated_by": generated_by,
            "validators_passed": validators,
            "human_reviewed": False,
            "cross_check": "skipped_no_model",
        },
        "diff": diff,
    }


def _finding(
    category: str, severity: str, file: str, quote: str, line: int, diff: str
) -> dict[str, object]:
    """Return one exact-line finding record."""
    actual_line = _added_line(diff, file, quote)
    if line != actual_line:
        raise ValueError(f"{file}:{line} does not match the quote line {actual_line}.")
    return {
        "category": category,
        "severity": severity,
        "file": file,
        "line_start": line,
        "line_end": line,
        "quote": quote,
    }


def _added_line(diff: str, file: str, quote: str) -> int:
    """Find the added line containing an exact finding quote."""
    for hunk in parse_diff(diff):
        if hunk.file != file:
            continue
        for line in hunk.added:
            if quote in line.text:
                return line.line_no
    raise ValueError(f"No added line in {file} contains {quote!r}.")


def split_for_id(case_id: str) -> str:
    """Use the fixed DECISIONS #19 SHA-256 split rule."""
    import hashlib

    return "dev" if int(hashlib.sha256(case_id.encode()).hexdigest(), 16) % 100 < 60 else "test"
