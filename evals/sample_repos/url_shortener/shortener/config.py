# Configuration for the sample URL-shortener.
# A single environment variable controls the public URL prefix.

import os
from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass(frozen=True)
class Settings:
    """Settings needed to construct public short links."""

    public_base_url: str


def load_settings() -> Settings:
    """Load and normalize the public base URL."""
    base_url = os.environ.get("SHORTENER_BASE_URL", "https://short.example")
    return Settings(public_base_url=base_url.rstrip("/"))


def is_http_url(value: str) -> bool:
    """Accept absolute HTTP and HTTPS URLs with a hostname."""
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
