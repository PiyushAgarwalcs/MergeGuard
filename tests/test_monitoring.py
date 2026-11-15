# Covers persisted shadow summaries and the shadow-report CLI command.

import json

from typer.testing import CliRunner

from mergeguard import storage
from mergeguard.cli import app
from mergeguard.monitoring import shadow_report
from mergeguard.storage import connect, insert_event, insert_feedback, insert_finding, insert_run


def _seed_monitoring_db(path):
    connection = connect(path)
    try:
        insert_run(
            "shadow-1", "acme/widget", 4, "sha", outcome="needs_human", connection=connection
        )
        insert_event("shadow-1", "github", "published", {"status": "shadow"}, connection=connection)
        insert_finding(
            "shadow-1",
            {"id": "F-1", "category": "injection", "severity": "high"},
            connection=connection,
        )
        insert_finding(
            "shadow-1",
            {"id": "F-2", "category": "injection", "severity": "medium"},
            connection=connection,
        )
        insert_feedback("shadow-1", "F-1", "dismiss", "alice", "false alarm", connection=connection)
        insert_run("blocked-1", "acme/widget", 5, "sha2", outcome="block", connection=connection)
        insert_feedback("blocked-1", "", "approve", "bob", "reviewed", connection=connection)
    finally:
        connection.close()


def test_shadow_report_summarizes_dismissals_and_approvals(tmp_path, monkeypatch):
    database = tmp_path / "monitor.db"
    _seed_monitoring_db(database)
    monkeypatch.setattr(storage, "DATABASE_PATH", str(database))

    report = shadow_report()

    assert report["shadow_run_count"] == 1
    assert report["categories"] == [
        {"category": "injection", "shown": 2, "dismissed": 1, "dismissal_rate": 0.5}
    ]
    assert report["approve_after_block"][0]["run_id"] == "blocked-1"


def test_shadow_report_command_emits_json(tmp_path, monkeypatch):
    database = tmp_path / "cli-monitor.db"
    _seed_monitoring_db(database)
    monkeypatch.setattr(storage, "DATABASE_PATH", str(database))

    result = CliRunner().invoke(app, ["shadow-report"])

    assert result.exit_code == 0
    assert json.loads(result.stdout)["shadow_run_count"] == 1
