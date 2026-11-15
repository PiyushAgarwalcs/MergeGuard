# Examples of URL-shortener behavior and safe URL handling.
# A temporary database prevents state from leaking between tests.

import pytest
from shortener.api import ShortenerApi
from shortener.preview import fetch_text, preview_title, safe_host_label
from shortener.store import initialize


@pytest.fixture
def api(tmp_path) -> ShortenerApi:
    """Provide an initialized shortener API with a temporary database."""
    database_path = str(tmp_path / "shortener.sqlite")
    initialize(database_path)
    return ShortenerApi(database_path, "local-test-token")


def test_create_resolve_and_track_visit(api: ShortenerApi) -> None:
    """A created code resolves to its original destination."""
    code = api.create("local-test-token", "alice", "https://example.test/a")

    assert code.isalnum()
    assert api.redirect_target(code) == "https://example.test/a"
    assert api.list("local-test-token", "alice")[0]["visits"] == 1


def test_owner_can_delete_but_other_owner_cannot(api: ShortenerApi) -> None:
    """A mapping cannot be deleted by a different owner."""
    code = api.create("local-test-token", "alice", "http://example.test/")

    assert not api.delete("local-test-token", "bob", code)
    assert api.delete("local-test-token", "alice", code)


def test_non_http_destination_is_rejected(api: ShortenerApi) -> None:
    """Only HTTP and HTTPS destinations are accepted."""
    with pytest.raises(ValueError, match="HTTP"):
        api.create("local-test-token", "alice", "file:///etc/passwd")


def test_preview_validates_before_calling_fetcher() -> None:
    """Invalid URL schemes never reach the injected network function."""
    called = False

    def fetch(_: str) -> str:
        nonlocal called
        called = True
        return "title"

    with pytest.raises(ValueError):
        preview_title("ftp://example.test/file", fetch, {"example.test"})
    assert not called


def test_host_label_excludes_userinfo_and_path() -> None:
    """Display labels contain only the parsed hostname."""
    assert safe_host_label("https://user:pass@example.test/private") == "example.test"


def test_stats_are_scoped_to_authenticated_owner(api: ShortenerApi) -> None:
    """Visit counts and link totals are isolated by owner."""
    code = api.create("local-test-token", "alice", "https://example.test/a")
    api.redirect_target(code)
    api.create("local-test-token", "bob", "https://example.test/b")

    assert api.stats("local-test-token", "alice") == {"links": 1, "visits": 1}
    assert api.stats("local-test-token", "bob") == {"links": 1, "visits": 0}


def test_empty_configured_token_never_authorizes(tmp_path) -> None:
    """A missing deployment token does not permit an empty credential."""
    from shortener.api import ShortenerApi

    api = ShortenerApi(str(tmp_path / "shortener.sqlite"), "")
    with pytest.raises(PermissionError):
        api.list("", "alice")


def test_malformed_public_code_does_not_query_storage(api: ShortenerApi) -> None:
    """Invalid path characters are rejected before database access."""
    assert api.redirect_target("../private") is None


def test_code_collision_retries_with_a_fresh_code(
    api: ShortenerApi, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A duplicate generated code does not prevent later allocation."""
    from shortener import service

    generated = iter(["samecode", "freshcode"])
    monkeypatch.setattr(service, "_new_code", lambda: next(generated))
    api.create("local-test-token", "alice", "https://example.test/first")

    code = api.create("local-test-token", "bob", "https://example.test/second")

    assert code == "freshcode"


def test_preview_calls_fetcher_for_valid_http_url() -> None:
    """Valid HTTP destinations are passed to the injected fetcher."""
    requested: list[str] = []

    def fetch(url: str) -> str:
        requested.append(url)
        return "Example title"

    assert preview_title("https://example.test/page", fetch, {"example.test"}) == "Example title"
    assert requested == ["https://example.test/page"]


def test_credentials_are_required_for_owner_operations(api: ShortenerApi) -> None:
    """Owner-scoped links cannot be listed without valid credentials."""
    with pytest.raises(PermissionError):
        api.list("wrong-token", "alice")


def test_empty_owner_is_rejected(api: ShortenerApi) -> None:
    """An authenticated request still requires a non-empty owner."""
    with pytest.raises(PermissionError):
        api.list("local-test-token", " ")


def test_listing_does_not_expose_other_owners_links(api: ShortenerApi) -> None:
    """Each owner sees only their own shortened destinations."""
    api.create("local-test-token", "alice", "https://alice.example/")
    api.create("local-test-token", "bob", "https://bob.example/")

    links = api.list("local-test-token", "alice")

    assert len(links) == 1
    assert links[0]["destination"] == "https://alice.example/"


def test_unknown_code_returns_no_destination(api: ShortenerApi) -> None:
    """Unknown well-formed codes produce a normal missing result."""
    assert api.redirect_target("unknown1") is None


def test_resolving_a_link_does_not_change_its_owner(api: ShortenerApi) -> None:
    """Public visits do not change who may manage a mapping."""
    code = api.create("local-test-token", "alice", "https://example.test/page")

    assert api.redirect_target(code) == "https://example.test/page"
    assert api.list("local-test-token", "bob") == []
    assert not api.delete("local-test-token", "bob", code)


def test_deleting_link_updates_owner_statistics(api: ShortenerApi) -> None:
    """Removed mappings no longer appear in aggregate owner counts."""
    code = api.create("local-test-token", "alice", "https://example.test/")
    api.redirect_target(code)
    assert api.delete("local-test-token", "alice", code)

    assert api.stats("local-test-token", "alice") == {"links": 0, "visits": 0}


def test_preview_rejects_url_without_hostname() -> None:
    """A URL with no authority is rejected before fetching."""
    with pytest.raises(ValueError):
        preview_title("https:///path", lambda _: "unreachable", {"example.test"})


def test_preview_rejects_host_outside_allowlist() -> None:
    """Disallowed hosts never reach the injected fetcher."""
    with pytest.raises(ValueError, match="not allowed"):
        preview_title("https://internal.example/", lambda _: "unreachable", set())


def test_fetch_text_uses_tls_and_response_size_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The HTTP helper verifies TLS and truncates oversized response content."""
    import httpx
    from shortener import preview

    requested: list[dict[str, object]] = []
    response = httpx.Response(
        200,
        text="x" * (preview.MAX_RESPONSE_CHARACTERS + 10),
        request=httpx.Request("GET", "https://example.test/"),
    )

    def fake_get(url: str, **kwargs: object) -> httpx.Response:
        requested.append({"url": url, **kwargs})
        return response

    monkeypatch.setattr(preview.httpx, "get", fake_get)
    text = fetch_text("https://example.test/", {"example.test"})

    assert len(text) == preview.MAX_RESPONSE_CHARACTERS
    assert requested[0]["verify"] is True


def test_fetch_text_does_not_request_disallowed_host(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Host policy is checked before any outbound request."""
    from shortener import preview

    monkeypatch.setattr(
        preview.httpx,
        "get",
        lambda *_args, **_kwargs: pytest.fail("unexpected network request"),
    )
    with pytest.raises(ValueError, match="not allowed"):
        fetch_text("https://internal.example/", {"public.example"})


def test_failed_delete_does_not_change_owner_statistics(api: ShortenerApi) -> None:
    """A different owner's deletion attempt leaves the mapping intact."""
    code = api.create("local-test-token", "alice", "https://example.test/")

    assert not api.delete("local-test-token", "bob", code)
    assert api.stats("local-test-token", "alice") == {"links": 1, "visits": 0}
