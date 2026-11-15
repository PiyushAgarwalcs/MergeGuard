# Context-collector examples with an independently known tiny call graph.

from __future__ import annotations

import tempfile
from pathlib import Path

from evals.results import SuiteCaseResult
from mergeguard.checks.collect_context import collect_context


def evaluate_context_collector() -> tuple[float, list[SuiteCaseResult]]:
    """Check changed symbols, callers, tests, siblings, CI and missing files."""
    with tempfile.TemporaryDirectory(prefix="mergeguard-context-eval-") as temporary:
        root = Path(temporary)
        (root / "pkg").mkdir()
        (root / "tests").mkdir()
        (root / "pkg" / "service.py").write_text(
            "def changed(value):\n    return normalize(value)\n\n"
            "def normalize(value):\n    return value.strip()\n",
            encoding="utf-8",
        )
        (root / "pkg" / "api.py").write_text(
            "from pkg.service import changed\n\n"
            "def endpoint(value):\n    return changed(value)\n",
            encoding="utf-8",
        )
        (root / "tests" / "test_service.py").write_text(
            "from pkg.service import changed\n\ndef test_changed():\n    assert changed(' x ') == 'x'\n",
            encoding="utf-8",
        )
        diff = "diff --git a/pkg/service.py b/pkg/service.py\n+def changed(value):\n"
        context = collect_context(root, ["pkg/service.py"], diff, "passing")
        kinds = {block.kind for block in context.blocks}
        expected = {
            "caller": True,
            "test": True,
            "sibling": True,
            "ci": True,
            "source_file": ["pkg/service.py"],
        }
        actual = {
            "caller": "caller" in kinds,
            "test": "test" in kinds,
            "sibling": "sibling" in kinds,
            "ci": "ci" in kinds,
            "source_file": context.changed_source_files,
        }
        cases = [
            SuiteCaseResult(
                "l1-context-known-call-graph",
                1,
                actual == expected and context.ci_status == "passing",
                expected,
                actual,
                {"component": "context_collector"},
            ),
        ]
        missing = collect_context(root, ["pkg/service.py"], diff)
        cases.append(
            SuiteCaseResult(
                "l1-context-missing-ci",
                1,
                missing.ci_status == "missing",
                {"ci_status": "missing"},
                {"ci_status": missing.ci_status},
                {"component": "context_collector"},
            )
        )
    return sum(case.passed for case in cases) / len(cases), cases
