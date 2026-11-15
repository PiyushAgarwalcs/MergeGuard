# Parses model replies and validates object or list outputs with Pydantic.
# Code fences and short prose prefixes are tolerated without executing content.

from __future__ import annotations

import json
import re
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

ModelT = TypeVar("ModelT", bound=BaseModel)
FENCE_PATTERN = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.IGNORECASE | re.DOTALL)


class InvalidModelOutput(ValueError):
    """Raised when a reply cannot be parsed or validated against its schema."""


def parse_json_reply(reply: str) -> Any:
    """Parse JSON from a fenced reply or a short prose-prefixed answer."""
    candidate = reply.strip()
    fence = FENCE_PATTERN.match(candidate)
    if fence:
        candidate = fence.group(1).strip()
    start = min(
        (index for index in (candidate.find("["), candidate.find("{")) if index >= 0),
        default=-1,
    )
    if start < 0:
        raise InvalidModelOutput("Reply does not contain a JSON object or array.")
    try:
        value, _ = json.JSONDecoder().raw_decode(candidate[start:])
    except json.JSONDecodeError as error:
        raise InvalidModelOutput(f"Reply contains invalid JSON: {error.msg}.") from error
    return value


def validate_list(reply: str, model: type[ModelT]) -> list[ModelT]:
    """Validate a JSON array as individual Pydantic model instances."""
    value = parse_json_reply(reply)
    if not isinstance(value, list):
        raise InvalidModelOutput("Expected a JSON array.")
    try:
        return [model.model_validate(item) for item in value]
    except (ValidationError, TypeError) as error:
        raise InvalidModelOutput(f"Array item validation failed: {error}.") from error


def validate_object(reply: str, model: type[ModelT]) -> ModelT:
    """Validate a JSON object as one Pydantic model instance."""
    value = parse_json_reply(reply)
    if not isinstance(value, dict):
        raise InvalidModelOutput("Expected a JSON object.")
    try:
        return model.model_validate(value)
    except ValidationError as error:
        raise InvalidModelOutput(f"Object validation failed: {error}.") from error
