# Tests saved-run comparisons, paired intervals, flipped cases and baseline JSON.
# Each test uses an isolated SQLite database so runs cannot leak across examples.

from __future__ import annotations

import json
from pathlib import Path

import pytest

from evals.baseline import save_baselines
from evals.compare import compare_runs, render_markdown
from evals.results import SuiteCaseResult, SuiteResult, save_suite_result
from mergeguard.storage import connect, list_eval_runs


def _save_run(connection, run_id: str, values: list[tuple[str, float, str]]) -> None:
    cases = tuple(
        SuiteCaseResult(
            case_id=case_id,
            repeat=1,
            passed=outcome == "pass",
            expected={"outcome": "pass"},
            actual={"outcome": outcome},
            metrics={"recall": score},
        )
        for case_id, score, outcome in values
    )
    save_suite_result(
        SuiteResult(
            layer="pipeline",
            dataset_version="v0.1",
            repeats=1,
            metrics={"recall": sum(case.metrics["recall"] for case in cases) / len(cases)},
            cases=cases,
            eval_run_id=run_id,
        ),
        connection=connection,
    )


def test_compare_runs_reports_paired_interval_and_flipped_cases(tmp_path: Path) -> None:
    connection = connect(tmp_path / "compare.db")
    _save_run(connection, "baseline", [("case-a", 0.2, "pass"), ("case-b", 0.4, "pass")])
    _save_run(connection, "candidate", [("case-a", 0.4, "block"), ("case-b", 0.6, "pass")])

    comparison = compare_runs("baseline", "candidate", connection=connection)
    markdown = render_markdown(comparison)

    assert comparison["metrics"]["recall"]["delta"] == pytest.approx(0.2)
    assert comparison["metrics"]["recall"]["interval"] == pytest.approx([0.2, 0.2])
    assert comparison["flipped_cases"] == [
        {"case_id": "case-a", "repeat": 1, "baseline": "pass", "candidate": "block"}
    ]
    assert "Flipped cases" in markdown and "case-a" in markdown
    connection.close()


def test_save_baseline_writes_metadata_and_marks_selected_run(tmp_path: Path) -> None:
    database = connect(tmp_path / "baseline.db")
    _save_run(database, "saved-run", [("case-a", 0.75, "pass")])
    output = tmp_path / "baselines" / "main.json"

    payload = save_baselines(output, connection=database)

    written = json.loads(output.read_text(encoding="utf-8"))
    assert payload == written
    assert written["layers"]["pipeline"]["eval_run_id"] == "saved-run"
    assert written["layers"]["pipeline"]["results"][0]["metrics"] == {"recall": 0.75}
    assert list_eval_runs(connection=database)[0]["is_baseline"] == 1
    database.close()


def test_compare_rejects_runs_from_different_layers(tmp_path: Path) -> None:
    connection = connect(tmp_path / "different-layers.db")
    _save_run(connection, "baseline", [("case-a", 0.2, "pass")])
    save_suite_result(
        SuiteResult("components", "v0.1", 1, {}, (), eval_run_id="candidate"),
        connection=connection,
    )

    with pytest.raises(ValueError, match="same layer"):
        compare_runs("baseline", "candidate", connection=connection)
    connection.close()


def test_eval_cli_compare_prints_markdown(tmp_path: Path, monkeypatch, capsys) -> None:
    from evals import run as eval_runner
    from mergeguard import storage

    monkeypatch.setattr(storage, "DATABASE_PATH", str(tmp_path / "cli-compare.db"))
    database = connect()
    _save_run(database, "baseline", [("case-a", 0.2, "pass")])
    _save_run(database, "candidate", [("case-a", 0.5, "pass")])
    database.close()

    assert eval_runner.main(["compare", "baseline", "candidate"]) == 0
    assert "Evaluation comparison: pipeline" in capsys.readouterr().out


def test_eval_cli_baseline_save_prints_selected_layers(tmp_path: Path, monkeypatch, capsys) -> None:
    from evals import run as eval_runner
    from mergeguard import storage

    monkeypatch.setattr(storage, "DATABASE_PATH", str(tmp_path / "cli-baseline.db"))
    monkeypatch.setattr(eval_runner, "BASELINE_PATH", tmp_path / "main.json")
    database = connect()
    _save_run(database, "saved-run", [("case-a", 0.75, "pass")])
    database.close()

    assert eval_runner.main(["baseline", "save"]) == 0
    assert '"pipeline"' in capsys.readouterr().out
    assert (tmp_path / "main.json").is_file()
