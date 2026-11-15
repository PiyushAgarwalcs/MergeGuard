# Smoke tests every dashboard page against populated and empty databases.
# Database selection uses an environment path resolved by the query layer.

from pathlib import Path

from streamlit.testing.v1 import AppTest

from mergeguard.storage import connect
from tests.make_sample_db import build_sample_db

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PAGE_FILES = (
    REPOSITORY_ROOT / "dashboard" / "app.py",
    REPOSITORY_ROOT / "dashboard" / "pages" / "1_Overview.py",
    REPOSITORY_ROOT / "dashboard" / "pages" / "4_Case_Explorer.py",
    REPOSITORY_ROOT / "dashboard" / "pages" / "9_Dataset.py",
)


def test_all_dashboard_pages_run_on_sample_database(tmp_path, monkeypatch):
    """Run every page with one saved evaluation result."""
    sample_path = build_sample_db(tmp_path / "sample.db")
    monkeypatch.setenv("DATABASE_PATH", str(sample_path))
    for page in PAGE_FILES:
        app = AppTest.from_file(str(page), default_timeout=30).run()
        assert not app.exception, f"{page.name}: {app.exception}"


def test_all_dashboard_pages_run_on_empty_database(tmp_path, monkeypatch):
    """Run every page when the SQLite schema exists but contains no rows."""
    empty_path = tmp_path / "empty.db"
    connection = connect(empty_path)
    connection.close()
    monkeypatch.setenv("DATABASE_PATH", str(empty_path))
    for page in PAGE_FILES:
        app = AppTest.from_file(str(page), default_timeout=30).run()
        assert not app.exception, f"{page.name}: {app.exception}"
