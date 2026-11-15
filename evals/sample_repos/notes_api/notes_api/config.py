# Configuration for the sample notes service.
# Environment values keep deployment-specific settings out of source code.

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    """Settings required by the notes service."""

    database_path: str
    api_token: str


def load_settings() -> Settings:
    """Load settings from the process environment."""
    return Settings(
        database_path=os.environ.get("NOTES_DATABASE", "notes.db"),
        api_token=os.environ.get("NOTES_API_TOKEN", ""),
    )
