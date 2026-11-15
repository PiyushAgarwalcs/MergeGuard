# Reviews changed behavior for concrete correctness defects.
# Model output is restricted to the correctness category family.

from __future__ import annotations

import json
from typing import Any, Literal

from openai import OpenAIError
from pydantic import ConfigDict

from mergeguard import tracing
from mergeguard.llm import (
    InvalidModelOutput,
    LLMDisabled,
    MissingCredentials,
    ReplayMiss,
    ask_for_list,
    load_prompt,
)
from mergeguard.llm_fake import ScriptedLLM
from mergeguard.models import Finding, ReviewContext, ReviewState, Source

PROMPT_NAME = "correctness_reviewer.v1"


class CorrectnessFinding(Finding):
    """Finding restricted to correctness categories and source."""

    model_config = ConfigDict(extra="forbid")

    source: Literal[Source.CORRECTNESS]
    category: Literal[
        "off_by_one",
        "wrong_condition",
        "missing_null_check",
        "resource_leak",
        "swallowed_exception",
        "wrong_default",
    ]


def run(state: ReviewState, *, client: ScriptedLLM | None = None) -> dict[str, Any]:
    """Review changed logic and return correctness findings or failure status."""
    pr = state.get("pr")
    if pr is None:
        return {"findings": [], "complete": False}
    context = state.get("context", ReviewContext(ci_status="missing"))
    prompt = load_prompt(
        PROMPT_NAME,
        diff=pr.diff,
        context=json.dumps(context.model_dump(), sort_keys=True, ensure_ascii=False),
    )
    try:
        findings = ask_for_list(
            prompt,
            CorrectnessFinding,
            agent="correctness_reviewer",
            client=client,
            run_id=state.get("run_id"),
        )
    except (
        InvalidModelOutput,
        LLMDisabled,
        MissingCredentials,
        OpenAIError,
        ReplayMiss,
        RuntimeError,
        TimeoutError,
    ) as error:
        tracing.record(
            state.get("run_id", "llm-unscoped"),
            "correctness_reviewer",
            "agent_failed",
            {"error_type": type(error).__name__},
        )
        return {"findings": [], "complete": False}
    return {"findings": findings, "complete": True}
