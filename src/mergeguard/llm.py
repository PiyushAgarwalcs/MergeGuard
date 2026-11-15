# mergeguard.llm
# Contains all model-client logic and cache/replay behavior for LLM access.

from __future__ import annotations

from typing import Any


def load_prompt(name: str, **values: Any) -> str:
    return f"prompt:{name}:{values}"


def ask_for_list(prompt: str, model: type[Any], agent: str) -> list[Any]:
    return []


def ask_for_object(prompt: str, model: type[Any], agent: str) -> Any:
    return model()
