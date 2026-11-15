# Evaluation result contracts and persistence adapters.
# Suite metadata and every case outcome are saved together for reconstruction.

from __future__ import annotations

import json
import subprocess
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from mergeguard.storage import insert_eval_bundle


@dataclass(frozen=True)
class SuiteCaseResult:
    """One case outcome from one repeat of a suite."""

    case_id: str
    repeat: int
    passed: bool
    expected: dict[str, Any]
    actual: dict[str, Any]
    metrics: dict[str, Any] = field(default_factory=dict)
    run_id: str | None = None


@dataclass(frozen=True)
class SuiteResult:
    """Complete suite output with enough metadata to reproduce its run."""

    layer: str
    dataset_version: str
    repeats: int
    metrics: dict[str, Any]
    cases: tuple[SuiteCaseResult, ...]
    prompt_versions: dict[str, str] = field(default_factory=dict)
    model_config: dict[str, Any] = field(default_factory=dict)
    eval_run_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    is_baseline: bool = False
    started_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat(timespec="seconds"))


def git_code_version(repository: Path | None = None) -> str:
    """Return the current Git commit hash, or `unknown` outside a Git checkout."""
    root = repository or Path(__file__).resolve().parents[1]
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            capture_output=True,
            check=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    return result.stdout.strip() or "unknown"


def save_suite_result(
    result: SuiteResult,
    *,
    code_version: str | None = None,
    connection: Any = None,
) -> dict[str, Any]:
    """Persist a suite and all case outcomes atomically in MergeGuard SQLite."""
    if result.repeats < 1:
        raise ValueError("A suite must have at least one repeat.")
    if any(case.repeat < 1 or case.repeat > result.repeats for case in result.cases):
        raise ValueError("Case repeat is outside the suite repeat count.")
    rows = [
        {
            "case_id": case.case_id,
            "repeat": case.repeat,
            "passed": int(case.passed),
            "expected": _json(case.expected),
            "actual": _json(case.actual),
            "metrics": _json(case.metrics),
            "run_id": case.run_id,
        }
        for case in result.cases
    ]
    return insert_eval_bundle(
        {
            "eval_run_id": result.eval_run_id,
            "started_at": result.started_at,
            "layer": result.layer,
            "dataset_version": result.dataset_version,
            "code_version": code_version or git_code_version(),
            "prompt_versions": _json(result.prompt_versions),
            "model_config": _json(result.model_config),
            "repeats": result.repeats,
            "is_baseline": int(result.is_baseline),
            "summary": _json(result.metrics),
        },
        rows,
        connection=connection,
    )


def _json(value: Any) -> str:
    """Serialize evaluation values consistently for SQLite text columns."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
