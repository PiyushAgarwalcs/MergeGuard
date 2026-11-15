# L1 diff parser cases from fixtures and generated boundary conditions.
# Expected ranges are fixed independently of the parser under evaluation.

from __future__ import annotations

from pathlib import Path

from evals.results import SuiteCaseResult
from mergeguard.checks.diff_parser import parse_diff

FIXTURE_ROOT = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "diffs"
FIXTURE_EXPECTATIONS: dict[str, tuple[tuple[int, int, tuple[int, ...]], ...]] = {
    "01_basic.diff": ((1, 4, (2,)),),
    "02_multihunk.diff": ((1, 3, (2,)), (10, 12, (11,))),
    "03_rename.diff": (),
    "04_binary.diff": (),
    "05_deleted_file.diff": ((1, 1, ()),),
    "06_crlf.diff": ((1, 3, (2,)),),
    "07_unicode.diff": ((1, 3, (2,)),),
    "08_no_newline.diff": ((1, 2, (1,)),),
    "09_context_only.diff": ((1, 4, (1,)),),
    "10_empty.diff": (),
    "11_nested_patch.diff": ((3, 8, (4, 5)), (20, 23, (21,))),
    "12_hunks_with_context.diff": ((5, 11, (7, 9)), (20, 21, (20,))),
    "13_special_chars.diff": ((1, 3, (2,)),),
    "14_large_hunk.diff": ((1, 24, (3, 4, 5)),),
    "15_minimal_rename.diff": ((1, 1, (1,)),),
}


def evaluate_diff_parser() -> tuple[float, list[SuiteCaseResult]]:
    """Check 15 tricky fixtures plus 35 independently labeled generated hunks."""
    cases: list[tuple[str, str, tuple[tuple[int, int, tuple[int, ...]], ...]]] = []
    for name, expected in FIXTURE_EXPECTATIONS.items():
        cases.append((name, (FIXTURE_ROOT / name).read_text(encoding="utf-8"), expected))
    cases.extend(_generated_cases())
    results = []
    for index, (case_id, diff, expected) in enumerate(cases):
        actual_hunks = parse_diff(diff)
        actual = tuple(
            (hunk.new_start, hunk.new_end, tuple(line.line_no for line in hunk.added))
            for hunk in actual_hunks
        )
        results.append(
            SuiteCaseResult(
                f"l1-diff-{index + 1:02d}-{case_id}",
                1,
                actual == expected,
                {"hunks": expected},
                {"hunks": actual},
                {"component": "diff_parser"},
            )
        )
    accuracy = sum(item.passed for item in results) / len(results)
    return accuracy, results


def _generated_cases() -> list[tuple[str, str, tuple[tuple[int, int, tuple[int, ...]], ...]]]:
    """Build 35 known line-range examples with changing starts and hunk sizes."""
    cases = []
    for index in range(1, 36):
        start = index * 13
        file = f"generated/case_{index:02d}.py"
        diff = (
            f"diff --git a/{file} b/{file}\n--- a/{file}\n+++ b/{file}\n"
            f"@@ -{start},1 +{start},2 @@\n context_{index}\n+added_{index}\n"
        )
        cases.append((f"generated-{index:02d}", diff, ((start, start + 1, (start + 1,)),)))
    return cases
