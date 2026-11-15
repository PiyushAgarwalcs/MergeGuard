# Tests static report rendering, storage reads and the nested CLI command.
# All report rows and paths are synthetic temporary fixtures.

import json
from typing import Any

from typer.testing import CliRunner

from evals.report import render_report, write_static_report
from mergeguard.cli import app
from mergeguard.storage import connect, insert_eval_bundle


def _run(run_id: str, layer: str, started_at: str, summary: dict[str, Any]) -> dict[str, Any]:
    """Create one evaluation row using the public storage contract."""
    return {
        "eval_run_id": run_id,
        "started_at": started_at,
        "layer": layer,
        "dataset_version": "v0.1",
        "code_version": "test-commit",
        "prompt_versions": "{}",
        "model_config": "{}",
        "repeats": 1,
        "is_baseline": 0,
        "summary": json.dumps(summary),
    }


def test_render_report_selects_latest_run_per_layer_and_escapes_values():
    """Show only each layer's newest run and escape untrusted stored text."""
    html = render_report(
        [
            _run("old", "components", "2026-01-01", {"thresholds_passed": False}),
            _run("new<script>", "components", "2026-02-01", {"thresholds_passed": True}),
            _run("agents", "agents", "2026-01-15", {"recall": 0.75}),
        ]
    )
    assert "new&lt;script&gt;" in html
    assert "<script>" not in html
    assert "old</h2>" not in html
    assert "components · PASS" in html
    assert "agents · UNGATED" in html


def test_render_report_has_empty_state_when_no_runs_exist():
    """Render a useful static page before the first evaluation."""
    assert "No evaluation runs have been saved yet." in render_report([])


def test_write_static_report_reads_saved_runs_and_writes_html(tmp_path):
    """Write a complete report using evaluation rows from SQLite."""
    database = tmp_path / "eval.db"
    connection = connect(database)
    try:
        insert_eval_bundle(
            _run("report-run", "components", "2026-02-01", {"thresholds_passed": True}),
            [],
            connection=connection,
        )
    finally:
        connection.close()
    output = tmp_path / "reports" / "latest.html"

    result = write_static_report(output, database)

    assert result == output
    contents = output.read_text(encoding="utf-8")
    assert "MergeGuard evaluation report" in contents
    assert "report-run" in contents


def test_eval_report_cli_writes_requested_destination(tmp_path, monkeypatch):
    """Expose report generation under the `mergeguard eval report` command."""
    database = tmp_path / "cli.db"
    connection = connect(database)
    connection.close()
    monkeypatch.setattr("mergeguard.storage.DATABASE_PATH", str(database))
    output = tmp_path / "cli-report.html"

    result = CliRunner().invoke(app, ["eval", "report", "--output", str(output)])

    assert result.exit_code == 0, result.output
    assert output.exists()
    assert "Wrote evaluation report" in result.output
