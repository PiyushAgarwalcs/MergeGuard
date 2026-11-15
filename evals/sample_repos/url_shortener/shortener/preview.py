# Safe destination preview helpers for the sample service.
# Network access is injected so callers can enforce an outbound policy.

from collections.abc import Callable
from urllib.parse import urlparse

import httpx

from shortener.config import is_http_url

FetchTitle = Callable[[str], str]
MAX_RESPONSE_CHARACTERS = 65_536


def preview_title(destination: str, fetch_title: FetchTitle, allowed_hosts: set[str]) -> str:
    """Fetch a destination title only after validating its URL scheme."""
    if not is_http_url(destination):
        raise ValueError("Only absolute HTTP and HTTPS URLs are allowed.")
    parsed = urlparse(destination)
    if parsed.hostname is None:
        raise ValueError("A destination hostname is required.")
    if parsed.hostname.lower() not in allowed_hosts:
        raise ValueError("The destination host is not allowed.")
    return fetch_title(destination)


def fetch_text(destination: str, allowed_hosts: set[str]) -> str:
    """Fetch a bounded response with TLS verification and an explicit host allowlist."""
    if not is_http_url(destination):
        raise ValueError("Only absolute HTTP and HTTPS URLs are allowed.")
    host = urlparse(destination).hostname
    if host is None or host.lower() not in allowed_hosts:
        raise ValueError("The destination host is not allowed.")
    response = httpx.get(destination, timeout=5.0, verify=True)
    response.raise_for_status()
    return response.text[:MAX_RESPONSE_CHARACTERS]


def safe_host_label(destination: str) -> str:
    """Return a hostname for display without URL credentials or path."""
    if not is_http_url(destination):
        raise ValueError("Invalid destination URL.")
    parsed = urlparse(destination)
    if parsed.hostname is None:
        raise ValueError("A destination hostname is required.")
    return parsed.hostname
