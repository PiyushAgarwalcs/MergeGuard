# Path validation for report inputs and outputs.
# Resolving paths prevents names from escaping the configured directories.

from pathlib import Path


def contained_path(directory: Path, name: str, suffix: str) -> Path:
    """Resolve a named file and ensure it stays inside its directory."""
    if not name or Path(name).name != name or name in {".", ".."}:
        raise ValueError("Expected a simple file name.")
    root = directory.resolve()
    candidate = (root / f"{name}{suffix}").resolve()
    if candidate.parent != root:
        raise ValueError("File path escapes the configured directory.")
    return candidate


def ensure_directory(directory: Path) -> Path:
    """Create a directory if needed and return its resolved path."""
    resolved = directory.resolve()
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved
