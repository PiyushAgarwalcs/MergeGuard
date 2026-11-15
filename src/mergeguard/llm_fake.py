# Scripted model transport for deterministic client and agent tests.
# Queued replies let tests cover validation retries without network access.

from __future__ import annotations

import json
from collections import deque
from typing import Any

from pydantic import BaseModel


class ScriptedLLM:
    """Return queued text replies or raise queued errors on successive calls."""

    def __init__(
        self,
        responses: list[str | dict[str, Any] | list[Any] | BaseModel | Exception],
    ) -> None:
        self._responses = deque(responses)
        self.calls = 0

    def complete(self, prompt: str, model: str, timeout: float) -> tuple[str, int, int]:
        """Consume one scripted response and return rough usage counts."""
        del model, timeout
        if not self._responses:
            raise RuntimeError("ScriptedLLM has no response queued.")
        self.calls += 1
        response = self._responses.popleft()
        if isinstance(response, Exception):
            raise response
        if isinstance(response, BaseModel):
            output = response.model_dump_json()
        elif isinstance(response, (dict, list)):
            output = json.dumps(response)
        else:
            output = response
        return output, max(1, len(prompt.split())), max(1, len(output.split()))
