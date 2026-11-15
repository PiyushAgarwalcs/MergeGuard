# Configuration for the sample CSV report utility.
# Paths and command settings come from environment variables at runtime.

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    """Runtime settings for report generation."""

    input_directory: Path
    output_directory: Path
    renderer: str


def load_settings() -> Settings:
    """Load input, output, and renderer settings."""
    return Settings(
        input_directory=Path(os.environ.get("REPORT_INPUT_DIR", "input")),
        output_directory=Path(os.environ.get("REPORT_OUTPUT_DIR", "reports")),
        renderer=os.environ.get("REPORT_RENDERER", ""),
    )
