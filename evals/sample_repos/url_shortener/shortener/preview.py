# Safe destination preview helpers for the sample service.
# Network access is injected so callers can enforce an outbound policy.

from collections.abc import Callable
from urllib.parse import urlparse

from shortener.config import is_http_url

FetchTitle = Callable[[str], str]


def preview_title(destination: str, fetch_title: FetchTitle) -> str:
    """Fetch a destination title only after validating its URL scheme."""
    if not is_http_url(destination):
        raise ValueError("Only absolute HTTP and HTTPS URLs are allowed.")
    parsed = urlparse(destination)
    if parsed.hostname is None:
        raise ValueError("A destination hostname is required.")
    return fetch_title(destination)


def safe_host_label(destination: str) -> str:
    """Return a hostname for display without URL credentials or path."""
    if not is_http_url(destination):
        raise ValueError("Invalid destination URL.")
    parsed = urlparse(destination)
    if parsed.hostname is None:
        raise ValueError("A destination hostname is required.")
    return parsed.hostname
