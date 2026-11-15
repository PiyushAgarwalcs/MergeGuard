# Reviews a pull request diff for concrete security vulnerabilities.
# Findings are schema-validated and failures make the review incomplete.

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

PROMPT_NAME = "security_reviewer.v1"


def run(
    state: ReviewState,
    *,
    client: ScriptedLLM | None = None,
) -> dict[str, Any]:
    """Review the PR diff and return findings or a visible incomplete status."""
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
            agent="security_reviewer",
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
            "security_reviewer",
            "agent_failed",
            {"error_type": type(error).__name__},
        )
        return {"findings": [], "complete": False}
    return {"findings": findings, "complete": True}
