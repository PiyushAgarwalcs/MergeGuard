# Evaluation command line and threshold gate.
# Suites register plain functions and return data saved by the shared result layer.

from __future__ import annotations

import argparse
import json
import math
import sqlite3
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from pathlib import Path

import yaml

from evals.config import EvalConfig
from evals.results import SuiteResult, save_suite_result
from evals.suites.agent_security import run as run_agent_security
from evals.suites.agents_other import run as run_agents_other
from evals.suites.components import run as run_components
from evals.suites.pipeline import run as run_pipeline
from mergeguard.storage import connect

THRESHOLDS_PATH = Path(__file__).with_name("thresholds.yml")


@dataclass(frozen=True)
class ThresholdCheck:
    """Outcome for each metric bar in one suite."""

    passed: bool
    bars: tuple[dict[str, object], ...]


@dataclass(frozen=True)
class EvalExecution:
    """Suite output together with threshold results and persistence id."""

    eval_run_id: str
    passed: bool
    metrics: dict[str, object]
    bars: tuple[dict[str, object], ...]
    case_count: int


SuiteRunner = Callable[[EvalConfig], SuiteResult]
SUITE_RUNNERS: dict[str, SuiteRunner] = {
    "agent_security": run_agent_security,
    "agents_other": run_agents_other,
    "components": run_components,
    "pipeline": run_pipeline,
}


def load_thresholds(path: Path = THRESHOLDS_PATH) -> dict[str, object]:
    """Read the YAML threshold document and check its top-level structure."""
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("suites"), dict):
        raise TypeError("Thresholds must define a suites mapping.")
    return payload


def check_thresholds(
    metrics: Mapping[str, object], bars: Mapping[str, Mapping[str, float]]
) -> ThresholdCheck:
    """Require each configured metric to satisfy its minimum or maximum bar."""
    results = []
    for name, limits in bars.items():
        actual = metrics.get(name)
        valid = isinstance(actual, (int, float)) and math.isfinite(float(actual))
        passed = valid
        expected: dict[str, float] = {}
        for operator, limit in limits.items():
            expected[operator] = float(limit)
            if operator == "min":
                passed = passed and valid and float(actual) >= limit
            elif operator == "max":
                passed = passed and valid and float(actual) <= limit
            else:
                raise ValueError(f"Unknown threshold operator: {operator}")
        if len(limits) != 1:
            raise ValueError(f"Each metric bar must use exactly one operator: {name}")
        results.append(
            {"metric": name, "actual": actual, "expected": expected, "passed": bool(passed)}
        )
    return ThresholdCheck(all(item["passed"] for item in results), tuple(results))


def execute_evaluation(
    config: EvalConfig,
    *,
    thresholds_path: Path = THRESHOLDS_PATH,
    runner: SuiteRunner | None = None,
    connection: sqlite3.Connection | None = None,
) -> EvalExecution:
    """Run a registered suite, gate its metrics, and save its results."""
    if config.repeats < 1 or (config.cases is not None and config.cases < 1):
        raise ValueError("Repeats and case limits must be positive.")
    selected_runner = runner or SUITE_RUNNERS.get(config.layer)
    if selected_runner is None:
        raise ValueError(f"No suite is registered for layer {config.layer!r}.")
    threshold_document = load_thresholds(thresholds_path)
    suites = threshold_document["suites"]
    bars = suites.get(config.layer, {})
    if not isinstance(bars, dict):
        raise TypeError(f"Threshold bars for {config.layer!r} must be a mapping.")
    suite_result = selected_runner(config)
    if suite_result.layer != config.layer:
        raise ValueError("Suite result layer does not match the requested layer.")
    threshold_check = check_thresholds(suite_result.metrics, bars)
    persisted = replace(
        suite_result,
        metrics={
            **suite_result.metrics,
            "thresholds_passed": threshold_check.passed,
            "threshold_bars": list(threshold_check.bars),
        },
    )
    owns_connection = connection is None
    store = connection or connect()
    try:
        save_suite_result(persisted, connection=store)
    finally:
        if owns_connection:
            store.close()
    return EvalExecution(
        suite_result.eval_run_id,
        threshold_check.passed,
        suite_result.metrics,
        threshold_check.bars,
        len(suite_result.cases),
    )


def main(argv: list[str] | None = None) -> int:
    """Parse the evaluation CLI, run one suite and report its gate result."""
    parser = argparse.ArgumentParser(prog="python -m evals.run")
    parser.add_argument("--layer", required=True)
    parser.add_argument("--split", choices=("dev", "test"))
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--cases", type=int)
    parser.add_argument("--mode", choices=("live", "replay"), default="replay")
    parser.add_argument("--dataset-version", default="v0.1")
    args = parser.parse_args(argv)
    config = EvalConfig(
        layer=args.layer,
        split=args.split,
        repeats=args.repeats,
        cases=args.cases,
        mode=args.mode,
        dataset_version=args.dataset_version,
    )
    try:
        execution = execute_evaluation(config)
    except (OSError, TypeError, ValueError) as error:
        print(json.dumps({"error": str(error)}), file=sys.stderr)
        return 1
    print(json.dumps(execution.__dict__, indent=2, sort_keys=True))
    return 0 if execution.passed else 1


if __name__ == "__main__":
    sys.exit(main())
