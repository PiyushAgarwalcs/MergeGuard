# Contains model-client access, output validation retries and call tracing.
# Tests inject ScriptedLLM; only this module reaches the OpenAI-compatible API.

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, TypeVar, cast

from pydantic import BaseModel

from mergeguard import tracing
from mergeguard.llm_cache import (
    DEFAULT_CACHE_DIR,
    CacheRecord,
    cache_key,
    prompt_hash,
    read_cache,
    write_cache,
)
from mergeguard.llm_fake import ScriptedLLM
from mergeguard.llm_json import InvalidModelOutput, validate_list, validate_object
from mergeguard.settings import settings

ModelT = TypeVar("ModelT", bound=BaseModel)
PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
MAX_VALIDATION_ATTEMPTS = 2
DEFAULT_TEMPERATURE = 0.0
_PROMPT_VERSIONS: dict[str, str] = {}


class ReplayMiss(RuntimeError):
    """Raised when replay mode has no cached response for a request."""


class LLMDisabled(RuntimeError):
    """Raised when model use is disabled by configuration."""


class MissingCredentials(RuntimeError):
    """Raised when live API access is requested without its configuration."""


def load_prompt(name: str, **values: Any) -> str:
    """Load one versioned Markdown prompt and replace named placeholders."""
    prompt_path = PROMPTS_DIR / f"{name}.md"
    prompt = prompt_path.read_text(encoding="utf-8")
    for key, value in values.items():
        replacement = str(value)
        prompt = prompt.replace("{{" + key + "}}", replacement)
        prompt = prompt.replace("{" + key + "}", replacement)
    _PROMPT_VERSIONS[prompt_hash(prompt)] = name
    return prompt


def ask_for_list(
    prompt: str,
    model: type[ModelT],
    agent: str,
    *,
    client: ScriptedLLM | None = None,
    run_id: str | None = None,
    cache_dir: Path = DEFAULT_CACHE_DIR,
) -> list[ModelT]:
    """Ask for a JSON list, validate each item and retry invalid output once."""
    return cast(list[ModelT], _ask(prompt, model, agent, "list", client, run_id, cache_dir))


def ask_for_object(
    prompt: str,
    model: type[ModelT],
    agent: str,
    *,
    client: ScriptedLLM | None = None,
    run_id: str | None = None,
    cache_dir: Path = DEFAULT_CACHE_DIR,
) -> ModelT:
    """Ask for one JSON object, validate it and retry invalid output once."""
    return cast(ModelT, _ask(prompt, model, agent, "object", client, run_id, cache_dir))


def _ask(
    prompt: str,
    model_schema: type[ModelT],
    agent: str,
    response_kind: str,
    client: ScriptedLLM | None,
    run_id: str | None,
    cache_dir: Path,
) -> Any:
    """Run a schema-validated request with one repair attempt."""
    if settings.LLM_MODE == "off":
        raise LLMDisabled("LLM_MODE=off prevents model requests.")
    model_name = _model_for_agent(agent)
    prompt_version = _PROMPT_VERSIONS.get(prompt_hash(prompt), "unversioned")
    request_id = run_id or "llm-unscoped"
    parameters: dict[str, object] = {
        "agent": agent,
        "response_kind": response_kind,
        "response_schema": model_schema.model_json_schema(),
        "temperature": DEFAULT_TEMPERATURE,
    }
    current_prompt = prompt
    for attempt in range(MAX_VALIDATION_ATTEMPTS):
        try:
            reply = _request(
                model_name,
                current_prompt,
                parameters,
                agent,
                prompt_version,
                request_id,
                client,
                cache_dir,
            )
            if response_kind == "list":
                return validate_list(reply, model_schema)
            return validate_object(reply, model_schema)
        except InvalidModelOutput as error:
            if attempt + 1 == MAX_VALIDATION_ATTEMPTS:
                raise
            current_prompt = _repair_prompt(prompt, str(error))
    raise InvalidModelOutput("Model output remained invalid after one retry.")


def _request(
    model: str,
    prompt: str,
    parameters: dict[str, object],
    agent: str,
    prompt_version: str,
    run_id: str,
    client: ScriptedLLM | None,
    cache_dir: Path,
) -> str:
    """Fetch, cache and trace one raw model response."""
    mode = settings.LLM_MODE
    key = cache_key(model, prompt, parameters)
    if mode == "replay":
        cached = read_cache(key, cache_dir)
        if cached is None:
            raise ReplayMiss(f"No cached LLM response for {agent} ({key}).")
        if cached.model != model or cached.prompt_hash != prompt_hash(prompt):
            raise ReplayMiss(f"Cached LLM response for {agent} does not match its request.")
        response = cached
        elapsed_ms = 0
    else:
        started = time.perf_counter()
        try:
            if client is not None:
                output, tokens_in, tokens_out = client.complete(
                    prompt, model, settings.AGENT_TIMEOUT_SECONDS
                )
            else:
                output, tokens_in, tokens_out = _call_openai_compatible(prompt, model)
        except Exception as error:
            tracing.record(run_id, agent, "llm_error", {"error": str(error)})
            raise
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        response = CacheRecord(
            model=model,
            prompt_hash=prompt_hash(prompt),
            output=output,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
        )
        if mode == "record":
            write_cache(key, response, cache_dir)
    tracing.record_llm_call(
        run_id,
        agent,
        model,
        prompt_version,
        response.tokens_in,
        response.tokens_out,
        elapsed_ms,
        response.output,
    )
    return response.output


def _call_openai_compatible(prompt: str, model: str) -> tuple[str, int, int]:
    """Call Chat Completions through the configured OpenAI-compatible endpoint."""
    if not settings.LLM_API_KEY or not settings.LLM_BASE_URL:
        raise MissingCredentials("LLM_API_KEY and LLM_BASE_URL are required for live mode.")
    from openai import OpenAI

    api = OpenAI(
        api_key=settings.LLM_API_KEY,
        base_url=settings.LLM_BASE_URL,
        timeout=settings.AGENT_TIMEOUT_SECONDS,
    )
    response = api.chat.completions.create(
        model=model,
        temperature=DEFAULT_TEMPERATURE,
        messages=[
            {"role": "system", "content": "Return only valid JSON matching the requested schema."},
            {"role": "user", "content": prompt},
        ],
    )
    output = response.choices[0].message.content or ""
    usage = response.usage
    return output, usage.prompt_tokens if usage else 0, usage.completion_tokens if usage else 0


def _model_for_agent(agent: str) -> str:
    """Select the configured model family for a specialist agent."""
    if agent == "skeptic":
        return settings.SKEPTIC_MODEL
    if agent == "cross_check":
        return settings.CROSS_CHECK_MODEL or settings.SKEPTIC_MODEL
    if agent == "judge":
        return settings.JUDGE_MODEL
    if agent in {"generator", "seed_issue"}:
        return settings.GENERATOR_MODEL
    return settings.REVIEWER_MODEL


def _repair_prompt(prompt: str, error: str) -> str:
    """Append one bounded schema error while preserving the original request."""
    return f"{prompt}\n\nYour previous reply was invalid: {error}\nReturn corrected JSON only."
