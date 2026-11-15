# Validates and stores raw model replies for record and replay modes.
# Cache keys include request parameters so incompatible calls never collide.

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

DEFAULT_CACHE_DIR = Path(".cache") / "llm"


class CacheRecord(BaseModel):
    """Validated cache entry containing only the raw reply and usage totals."""

    model_config = ConfigDict(extra="forbid")

    model: str
    prompt_hash: str
    output: str
    tokens_in: int = Field(ge=0)
    tokens_out: int = Field(ge=0)


def prompt_hash(prompt: str) -> str:
    """Return a stable SHA-256 digest of the full prompt text."""
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


def cache_key(model: str, prompt: str, parameters: dict[str, object]) -> str:
    """Hash the model, exact prompt and request parameters into a cache key."""
    request = {"model": model, "prompt": prompt, "parameters": parameters}
    serialized = json.dumps(request, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def read_cache(key: str, directory: Path = DEFAULT_CACHE_DIR) -> CacheRecord | None:
    """Return one validated cache entry, or None when it is not present."""
    path = directory / f"{key}.json"
    if not path.is_file():
        return None
    return CacheRecord.model_validate_json(path.read_text(encoding="utf-8"))


def write_cache(key: str, record: CacheRecord, directory: Path = DEFAULT_CACHE_DIR) -> Path:
    """Write a validated cache entry under its content-derived key."""
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{key}.json"
    path.write_text(record.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return path
