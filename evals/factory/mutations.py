# Test-verified correctness mutation generation.
# Only AST-selected edits that fail their isolated sample tests are retained.

from __future__ import annotations

import difflib
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

from evals.factory.mutation_ast import mutate_source
from evals.factory.mutation_specs import all_mutation_specs
from evals.factory.mutation_types import MutationCase, MutationSpec
from evals.factory.templates import SAMPLE_ROOT
from mergeguard.checks.diff_parser import parse_diff

TEST_DIRECTORIES = {
    "notes_api": "notes_tests",
    "url_shortener": "shortener_tests",
    "csv_report": "report_tests",
}
TEST_TIMEOUT_SECONDS = 30


def _render_mutation(spec: MutationSpec, sample_root: Path) -> MutationCase:
    """Create one minimal diff from an AST-selected source edit."""
    source_path = sample_root / spec.sample_repo / spec.file
    original = source_path.read_text(encoding="utf-8")
    content, edit = mutate_source(original, spec)
    diff_lines = difflib.unified_diff(
        original.splitlines(keepends=True),
        content.splitlines(keepends=True),
        fromfile=f"a/{spec.file}",
        tofile=f"b/{spec.file}",
        n=3,
    )
    diff = f"diff --git a/{spec.file} b/{spec.file}\n" + "".join(diff_lines)
    added = [
        line for hunk in parse_diff(diff) for line in hunk.added if edit.replacement in line.text
    ]
    if not added:
        raise ValueError(f"{spec.case_id}: mutation quote is not in the diff")
    line_number = added[0].line_no
    return MutationCase(
        spec.case_id,
        spec.category,
        spec.sample_repo,
        spec.file,
        content,
        diff,
        edit.replacement,
        line_number,
        line_number,
    )


def _run_sample_tests(app_root: Path, sample_repo: str) -> subprocess.CompletedProcess[str]:
    """Run one sample app's tests with no test code imported into this process."""
    test_directory = TEST_DIRECTORIES[sample_repo]
    try:
        return subprocess.run(
            [sys.executable, "-m", "pytest", "-q", test_directory],
            capture_output=True,
            check=False,
            cwd=app_root,
            text=True,
            timeout=TEST_TIMEOUT_SECONDS,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as error:
        raise RuntimeError(f"Sample tests could not complete: {error}") from error


def _mutation_fails_tests(case: MutationCase, sample_root: Path) -> bool:
    """Copy one sample app, install the mutation and require a test failure."""
    original_root = sample_root / case.sample_repo
    with tempfile.TemporaryDirectory(prefix="mergeguard-mutation-") as directory:
        app_root = Path(directory) / case.sample_repo
        shutil.copytree(
            original_root,
            app_root,
            ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"),
        )
        (app_root / case.file).write_text(case.content, encoding="utf-8")
        result = _run_sample_tests(app_root, case.sample_repo)
    return result.returncode != 0


def generate_mutations(sample_root: Path = SAMPLE_ROOT) -> list[MutationCase]:
    """Return only correctness mutations that make an existing test fail."""
    specs = all_mutation_specs()
    counts = Counter(spec.category for spec in specs)
    if len(specs) != 12 or set(counts.values()) != {2}:
        raise ValueError("The mutation plan must contain two cases per correctness category.")

    baseline_status: dict[str, bool] = {}
    mutations: list[MutationCase] = []
    for spec in specs:
        if spec.sample_repo not in baseline_status:
            baseline = _run_sample_tests(sample_root / spec.sample_repo, spec.sample_repo)
            baseline_status[spec.sample_repo] = baseline.returncode == 0
            if not baseline_status[spec.sample_repo]:
                raise RuntimeError(f"Base tests failed for {spec.sample_repo}.")
        case = _render_mutation(spec, sample_root)
        if _mutation_fails_tests(case, sample_root):
            mutations.append(case)
    return mutations
