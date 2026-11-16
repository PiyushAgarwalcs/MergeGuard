# Tests run persistence, structured tracing, privacy handling, and concurrent writes.

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import mergeguard.settings as settings_module
from mergeguard.storage import connect, get_events, get_run, insert_event, insert_run, list_runs
from mergeguard.tracing import record, record_llm_call


def _reset_db() -> None:
    path = Path("data/mergeguard.db")
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()


def test_storage_round_trip_and_trace() -> None:
    _reset_db()
    conn = connect()
    try:
        run_id = "run-1"
        insert_run(
            run_id,
            repo="demo/repo",
            pr_number=12,
            head_sha="abc123",
            status="running",
            outcome="pending",
            connection=conn,
        )
        insert_event(
            run_id,
            "security_reviewer",
            "decision",
            {"outcome": "needs_human"},
            connection=conn,
        )

        run = get_run(run_id, connection=conn)
        assert run is not None
        assert run["status"] == "running"
        events = get_events(run_id, connection=conn)
        assert events
        assert events[0]["kind"] == "decision"
        assert events[0]["payload"]["outcome"] == "needs_human"
    finally:
        conn.close()


def test_privacy_mode_hashes_diff_text(monkeypatch) -> None:
    _reset_db()
    monkeypatch.setattr(settings_module.settings, "PRIVACY_MODE", True)
    record(
        "run-privacy",
        "review",
        "decision",
        {"diff": "token = 'secret-123'\nprint(1)", "status": "ok"},
        repo="demo/repo",
        pr_number=2,
        head_sha="sha",
    )
    events = get_events("run-privacy")
    payload = events[0]["payload"]
    assert payload["diff"] != "token = 'secret-123'\nprint(1)"
    assert payload["status"] == "ok"


def test_record_llm_call_tracks_cost_and_hashes_output(monkeypatch) -> None:
    _reset_db()
    monkeypatch.setattr(settings_module.settings, "PRIVACY_MODE", True)
    event = record_llm_call(
        "run-llm",
        "security_reviewer",
        "gpt-4o-mini",
        "v1",
        250,
        125,
        300,
        "final answer",
    )
    assert event["tokens_in"] == 250
    assert event["tokens_out"] == 125
    assert event["model"] == "gpt-4o-mini"
    assert event["payload"]
    assert "final answer" not in event["payload"]


def test_concurrent_writers_do_not_corrupt_file() -> None:
    _reset_db()

    def writer(index: int) -> None:
        conn = connect()
        try:
            insert_run(
                f"run-{index}",
                repo="demo/repo",
                pr_number=index,
                head_sha=f"sha-{index}",
                status="done",
                outcome="pass",
                connection=conn,
            )
        finally:
            conn.close()

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(writer, range(12)))

    rows = list_runs()
    assert len(rows) == 12
