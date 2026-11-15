# Optional renderer integration for generated report files.
# A fixed argument list avoids shell interpretation of file paths.

import subprocess
from pathlib import Path


def render(renderer: str, report_path: Path) -> None:
    """Invoke an explicitly configured renderer for a report file."""
    if not renderer:
        return
    subprocess.run(
        [renderer, str(report_path)],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
