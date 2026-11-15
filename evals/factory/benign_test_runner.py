# Isolated sample-app test execution for benign dataset candidates.
# Grouped testing keeps validation fast while testing all composable changes.

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from collections import defaultdict
from pathlib import Path

from evals.factory.benign_types import ExampleCase
from evals.factory.diff_apply import apply_unified_diff
from evals.factory.mutations import TEST_DIRECTORIES, _run_sample_tests
from evals.factory.templates import SAMPLE_ROOT

HUNK_START = re.compile(r"^@@ -(\d+)")


def run_case_tests(
    case: ExampleCase, sample_root: Path = SAMPLE_ROOT
) -> subprocess.CompletedProcess[str]:
    """Run one changed sample app in a disposable copy."""
    with tempfile.TemporaryDirectory(prefix="mergeguard-benign-") as directory:
        app_root = _copy_app(case.sample_repo, sample_root, Path(directory))
        for file, content in case.changes:
            (app_root / file).write_text(content, encoding="utf-8")
        return _run_sample_tests(app_root, case.sample_repo)


def run_grouped_tests(cases: list[ExampleCase], sample_root: Path = SAMPLE_ROOT) -> dict[str, bool]:
    """Run combined Python changes once for each sample app."""
    cases_by_repo: dict[str, list[ExampleCase]] = defaultdict(list)
    for case in cases:
        cases_by_repo[case.sample_repo].append(case)
    return {
        repo: _run_group(repo_cases, sample_root).returncode == 0
        for repo, repo_cases in cases_by_repo.items()
    }


def _run_group(cases: list[ExampleCase], sample_root: Path) -> subprocess.CompletedProcess[str]:
    """Apply composable Python patches and run one app test suite."""
    sample_repo = cases[0].sample_repo
    with tempfile.TemporaryDirectory(prefix="mergeguard-benign-") as directory:
        app_root = _copy_app(sample_repo, sample_root, Path(directory))
        patches_by_file: dict[str, list[str]] = defaultdict(list)
        for case in cases:
            for file, patch in case.patches:
                if not file.endswith(".py"):
                    continue
                patches_by_file[file].append(patch)
        updates: dict[str, str] = {}
        for file, patches in patches_by_file.items():
            original = (sample_root / sample_repo / file).read_text(encoding="utf-8")
            current = original
            for patch in sorted(patches, key=_patch_start, reverse=True):
                current = apply_unified_diff(current, patch)
            updates[file] = current
        for file, content in updates.items():
            (app_root / file).write_text(content, encoding="utf-8")
        return _run_sample_tests(app_root, sample_repo)


def _patch_start(patch: str) -> int:
    """Return the base-file line where the first hunk starts."""
    header = next((line for line in patch.splitlines() if line.startswith("@@")), "")
    match = HUNK_START.match(header)
    if match is None:
        raise ValueError("Generated patch has no valid hunk header.")
    return int(match.group(1))


def _copy_app(sample_repo: str, sample_root: Path, directory: Path) -> Path:
    """Copy one registered sample application into a temporary directory."""
    if sample_repo not in TEST_DIRECTORIES:
        raise ValueError(f"Unknown sample repository {sample_repo}.")
    app_root = directory / sample_repo
    shutil.copytree(
        sample_root / sample_repo,
        app_root,
        ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"),
    )
    return app_root
