# Regression sentinels for URL-shortener correctness mutations.
# Public URL configuration and code length are stable service behavior.

import pytest
from shortener.api import ShortenerApi
from shortener.config import load_settings
from shortener.preview import preview_title
from shortener.store import initialize


def test_short_code_has_expected_length(tmp_path) -> None:
    """Generated short codes retain the configured fixed length."""
    database_path = str(tmp_path / "shortener.sqlite")
    initialize(database_path)
    api = ShortenerApi(database_path, "test-token")

    code = api.create("test-token", "alice", "https://example.test/")

    assert len(code) == 8


def test_default_public_base_url_uses_https(monkeypatch: pytest.MonkeyPatch) -> None:
    """The default public short-link base uses HTTPS."""
    monkeypatch.delenv("SHORTENER_BASE_URL", raising=False)

    assert load_settings().public_base_url == "https://short.example"


def test_preview_rejects_authority_without_hostname() -> None:
    """Malformed network authorities never reach the injected fetcher."""
    with pytest.raises(ValueError):
        preview_title("http://:80", lambda _: "unreachable", {"example.test"})
