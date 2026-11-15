# Reviews tests and test changes for missing or weakened coverage.
# Model output is restricted to the test-gap category family.

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

PROMPT_NAME = "test_reviewer.v1"


class ReviewFindingForTests(Finding):
    """Finding restricted to test-gap categories and source."""

    model_config = ConfigDict(extra="forbid")

    source: Literal[Source.TESTS]
    category: Literal["missing_test", "test_weakened", "assertion_removed"]


def run(state: ReviewState, *, client: ScriptedLLM | None = None) -> dict[str, Any]:
    """Review test coverage changes and return findings or failure status."""
    pr = state.get("pr")
    if pr is None:
        return {"findings": [], "complete": False}
    context = state.get("context", ReviewContext(ci_status="missing"))
    prompt = load_prompt(
        PROMPT_NAME,
        diff=pr.diff,
        context=json.dumps(context.model_dump(), sort_keys=True, ensure_ascii=False),
        ci_status=context.ci_status,
        changed_test_files=json.dumps(context.changed_test_files),
    )
    try:
        findings = ask_for_list(
            prompt,
            ReviewFindingForTests,
            agent="test_reviewer",
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
            "test_reviewer",
            "agent_failed",
            {"error_type": type(error).__name__},
        )
        return {"findings": [], "complete": False}
    return {"findings": findings, "complete": True}
