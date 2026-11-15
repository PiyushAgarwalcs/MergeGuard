# Reviews all allowed finding categories in one model request for ablations.
# The single-agent variant uses the same validated Finding response contract.

from __future__ import annotations

import json
from typing import Any

from openai import OpenAIError

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
from mergeguard.models import Finding, ReviewContext, ReviewState

PROMPT_NAME = "single_reviewer.v1"


def run(state: ReviewState, *, client: ScriptedLLM | None = None) -> dict[str, Any]:
    """Review the diff using all security, correctness, and test checklists."""
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
            Finding,
            agent="single_reviewer",
            client=client,
            run_id=state.get("run_id"),
        )
    except (
        InvalidModelOutput,
        LLMDisabled,
        MissingCredentials,
        OpenAIError,
        ReplayMiss,
        TimeoutError,
    ) as error:
        tracing.record(
            state.get("run_id", "llm-unscoped"),
            "single_reviewer",
            "agent_failed",
            {"error_type": type(error).__name__},
        )
        return {"findings": [], "complete": False}
    return {"findings": findings, "complete": True}
