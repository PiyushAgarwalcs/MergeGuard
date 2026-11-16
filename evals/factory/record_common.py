# evals.factory.record_common
# Builds shared evidence fields and deterministic dataset split IDs.

from __future__ import annotations

import hashlib

from mergeguard.checks.diff_parser import parse_diff


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
    return "dev" if int(hashlib.sha256(case_id.encode()).hexdigest(), 16) % 100 < 60 else "test"
